"""Bounded JSON and immutable, content-addressed evidence storage."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from tracemantle.io_limits import MAX_INGEST_BYTES, read_bounded_bytes


class EvidenceError(ValueError):
    """Unsupported, malformed or inconsistent evidence input."""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False, default=_json_default).encode('utf-8')


def _json_default(value: object) -> object:
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f'Unsupported JSON value: {type(value).__name__}')


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f'Duplicate JSON field {key!r}. Keep one value per field.')
        result[key] = value
    return result


def decode_json(raw: bytes | str, *, max_bytes: int = MAX_INGEST_BYTES) -> Any:
    if len(raw if isinstance(raw, bytes) else raw.encode('utf-8')) > max_bytes:
        raise EvidenceError(f'JSON exceeds the {max_bytes}-byte limit.')
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda x: _invalid_constant(x))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError(f'Invalid JSON: {exc}') from exc
    pending = [(value, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if depth > 40 or nodes > 100000:
            raise EvidenceError('JSON depth or node limit exceeded.')
        if isinstance(current, (dict, list)):
            pending.extend((item, depth + 1) for item in (current.values() if isinstance(current, dict) else current))
    return value


def _invalid_constant(value: str) -> Any:
    raise EvidenceError(f'Non-finite JSON constant {value!r} is unsupported.')


def read_json(path: Path, *, max_bytes: int = MAX_INGEST_BYTES) -> Any:
    return decode_json(read_bounded_bytes(path, max_bytes=max_bytes, what='JSON', error_cls=EvidenceError), max_bytes=max_bytes)


def outside_bundle(destination: Path, bundle: Path) -> None:
    if destination.resolve().is_relative_to(bundle.resolve()):
        raise EvidenceError(f'Evidence destination {destination} is inside the evaluated bundle. Select a directory outside {bundle}.')


def put_bytes(root: Path, raw: bytes, *, suffix: str = '.json') -> Path:
    """Publish a complete immutable object without replacing another writer's file."""
    root.mkdir(parents=True, exist_ok=True)
    target = root / (hashlib.sha256(raw).hexdigest() + suffix)
    fd, temp = tempfile.mkstemp(prefix='.pending-', dir=root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, target)
        except FileExistsError:
            existing = read_bounded_bytes(target, max_bytes=len(raw), what='Stored evidence', error_cls=EvidenceError)
            if existing != raw:
                raise EvidenceError(f'Existing immutable object at {target} has unexpected content. Preserve it and select a clean store.') from None
    finally:
        Path(temp).unlink(missing_ok=True)
    return target


def put_record(root: Path, record: object) -> Path:
    return put_bytes(root, canonical(record))
