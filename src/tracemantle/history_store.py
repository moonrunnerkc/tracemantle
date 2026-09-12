"""New history writes never update a shared ledger or alter a skill bundle."""
from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import asdict
from itertools import islice
from pathlib import Path
from typing import Any

from tracemantle import __version__
from tracemantle.bundle import create_manifest
from tracemantle.core.history import LedgerEntry, LedgerError, _entry_to_dict, load_ledger
from tracemantle.core.history_io import _entry_from_dict
from tracemantle.io_limits import MAX_LEDGER_BYTES, MAX_SCAN_BYTES, read_bounded_bytes
from tracemantle.parser import ParsedSkill
from tracemantle.storage import EvidenceError, decode_json, digest, outside_bundle, put_bytes, put_record


def history_identity(skill: ParsedSkill, options: dict[str, Any]) -> tuple[str, str]:
    manifest = create_manifest(skill.path.parent, document=skill)
    return manifest.sha256, digest({'document': asdict(skill.settings), 'options': options, 'checker_version': __version__})


def append_history(root: Path, skill: ParsedSkill, entry: LedgerEntry, identity: tuple[str, str]) -> Path:
    outside_bundle(root, skill.path.parent)
    return put_record(root, {'schema_version': 2, 'kind': 'validation-history', 'run_id': uuid.uuid4().hex,
                            'bundle_sha256': identity[0], 'configuration_sha256': identity[1], 'entry': _entry_to_dict(entry)})


def read_history_record(path: Path, *, max_bytes: int = MAX_LEDGER_BYTES) -> tuple[dict[str, Any], LedgerEntry, int]:
    try:
        raw = read_bounded_bytes(path, max_bytes=max_bytes, what="History record", error_cls=EvidenceError)
        data = decode_json(raw, max_bytes=max_bytes)
        fields = {'schema_version', 'kind', 'run_id', 'bundle_sha256', 'configuration_sha256', 'entry'}
        if not isinstance(data, dict) or set(data) != fields or type(data['schema_version']) is not int or data['schema_version'] != 2 or data['kind'] != 'validation-history':
            raise EvidenceError('Expected exactly the version-two validation-history fields.')
        if not isinstance(data['run_id'], str) or not data['run_id'] or len(data['run_id']) > 128:
            raise EvidenceError('History run_id must be a nonempty bounded string.')
        for field in ('bundle_sha256', 'configuration_sha256'):
            if not isinstance(data[field], str) or not re.fullmatch('[0-9a-f]{64}', data[field]):
                raise EvidenceError(f'History {field} requires a full SHA-256 digest.')
        if path.stem != digest(data):
            raise EvidenceError('History filename does not match its immutable content digest.')
        return data, _entry_from_dict(data['entry'], path), len(raw)
    except EvidenceError as exc:
        raise LedgerError(f'Malformed history record at {path}: {exc}. Preserve it for inspection.') from exc


def iter_history_records(root: Path) -> Iterator[tuple[dict[str, Any], LedgerEntry]]:
    paths = sorted(islice(root.glob('*.json'), 10001)) if root.is_dir() else []
    if len(paths) > 10000:
        raise LedgerError('History exceeds the 10000-record limit; archive older records.')
    total = 0
    for path in paths:
        data, entry, size = read_history_record(path, max_bytes=min(MAX_LEDGER_BYTES, MAX_SCAN_BYTES - total))
        total += size
        yield data, entry


def comparable_runs(root: Path, identity: tuple[str, str]) -> tuple[LedgerEntry, ...]:
    runs = [entry for data, entry in iter_history_records(root)
            if (data['bundle_sha256'], data['configuration_sha256']) == identity]
    return tuple(sorted(runs, key=lambda r: r.timestamp_utc))


def migrate_legacy(source: Path, destination: Path) -> dict[str, object]:
    outside_bundle(destination, source.parent)
    ledger = load_ledger(source)
    if ledger is None:
        raise EvidenceError(f'Legacy ledger {source} does not exist.')
    raw = read_bounded_bytes(source, max_bytes=MAX_LEDGER_BYTES, what='Legacy history', error_cls=EvidenceError)
    artifact = put_bytes(destination / 'sources', raw)
    records = []
    for index, entry in enumerate(ledger.runs):
        record = {'schema_version': 2, 'kind': 'legacy-history', 'source_sha256': artifact.stem,
                  'source_index': index, 'entry': _entry_to_dict(entry), 'comparison_state': 'unknown',
                  'reason': 'Version-one history lacks bundle, checker, fixture and execution identities.'}
        records.append(str(put_record(destination / 'records', record)))
    return {'source_preserved': str(source), 'source_copy': str(artifact), 'records': records, 'state': 'unknown'}
