"""CLI integration for bundle identity, evaluator imports and release comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tracemantle import __version__
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.core.history import LedgerError
from tracemantle.display import terminal
from tracemantle.evidence import evidence_from_dict
from tracemantle.formatters import _escape_data, _escape_property
from tracemantle.history_store import migrate_legacy
from tracemantle.io_limits import MAX_INGEST_BYTES, MAX_SCAN_BYTES, read_bounded_bytes
from tracemantle.policy import load_trusted_policy
from tracemantle.promptfoo import import_promptfoo
from tracemantle.storage import EvidenceError, decode_json, outside_bundle, put_bytes, put_record, read_json

COMMANDS = frozenset({'manifest', 'import-evidence', 'compare', 'migrate-history'})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='tracemantle', description='TraceMantle bundle and release evidence commands')
    commands = parser.add_subparsers(dest='command', required=True)
    manifest = commands.add_parser('manifest', help='Create a canonical bundle manifest')
    manifest.add_argument('bundle', type=Path)
    importer = commands.add_parser('import-evidence', help='Import a pinned Promptfoo export without executing it')
    importer.add_argument('source', type=Path)
    importer.add_argument('--bundle', type=Path, required=True)
    importer.add_argument('--bindings', type=Path, help='Explicit identity bindings for exported row IDs')
    importer.add_argument('--store', type=Path, required=True, help='Evidence store outside the bundle')
    comparison = commands.add_parser('compare', help='Compare bundles using policy/checkers from a trusted Git base')
    comparison.add_argument('baseline', type=Path)
    comparison.add_argument('candidate', type=Path)
    comparison.add_argument('--evidence', type=Path, action='append', default=[])
    comparison.add_argument('--trusted-root', type=Path, required=True)
    comparison.add_argument('--base-revision', required=True, help='Full trusted base commit SHA')
    comparison.add_argument('--policy-relative', default='pyproject.toml')
    migration = commands.add_parser('migrate-history', help='Copy legacy history explicitly, preserving its original')
    migration.add_argument('source', type=Path)
    migration.add_argument('--store', type=Path, required=True)
    for command in (manifest, importer, comparison, migration):
        command.add_argument('--format', choices=['text', 'json', 'github'], default='text')
        command.add_argument('--output', type=Path, help='Explicit output file; existing differing content is refused')
    return parser


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int, Path | None]:
    if args.command == 'manifest':
        manifest = create_manifest(args.bundle)
        return manifest.to_dict(), 0 if manifest.complete else 4, args.bundle / 'SKILL.md'
    if args.command == 'import-evidence':
        outside_bundle(args.store, args.bundle)
        manifest = create_manifest(args.bundle)
        raw = read_bounded_bytes(args.source, max_bytes=MAX_INGEST_BYTES, what='Promptfoo export', error_cls=EvidenceError)
        bindings = read_json(args.bindings) if args.bindings else {'schema_version': 1, 'rows': {}}
        imported = import_promptfoo(raw, bindings)
        files = {f.path: f.sha256 for f in manifest.files}
        for record in imported.records:
            if record.bundle_sha256 != manifest.sha256 or any(files.get(p) != sha for p, sha in record.inputs):
                raise EvidenceError('Import binding does not match the actual bundle or resource digests.')
        source = put_bytes(args.store / 'sources', raw)
        stored_records = [str(put_record(args.store / 'records', record.to_dict())) for record in imported.records]
        return {'artifact_sha256': imported.artifact_sha256, 'source_copy': str(source), 'records': stored_records,
                'issues': imported.issues, 'state': 'unknown', 'reason': 'Imported claims require trusted-base approval before behavioral gating.'}, 4, args.bundle / 'SKILL.md'
    if args.command == 'migrate-history':
        return migrate_legacy(args.source, args.store), 0, None
    baseline = create_manifest(args.baseline)
    candidate = create_manifest(args.candidate)
    policy = load_trusted_policy(args.trusted_root, args.base_revision, args.policy_relative)
    if len(args.evidence) > 10000:
        raise EvidenceError('At most 10000 evidence records may be compared.')
    evidence = []
    total = 0
    for path in args.evidence:
        raw = read_bounded_bytes(path, max_bytes=min(MAX_INGEST_BYTES, MAX_SCAN_BYTES - total), what='Evidence', error_cls=EvidenceError)
        total += len(raw)
        evidence.append(evidence_from_dict(decode_json(raw)))
    records = tuple(evidence)
    report = compare(baseline, candidate, records, policy)
    return report.to_dict(), report.exit_code, args.candidate / 'SKILL.md'


def render_product(payload: dict[str, Any], fmt: str, path: Path | None) -> str:
    if fmt == 'json':
        return json.dumps(payload, indent=2, ensure_ascii=True)
    result = payload['result']
    state = result.get('state', 'pass' if payload['exit_code'] == 0 else 'unknown')
    lines = [f"TraceMantle {payload['command']}: {state} (exit {payload['exit_code']})"]
    if payload['command'] == 'manifest' and 'bundle_sha256' in result:
        lines.append(f"Bundle {result['bundle_sha256']}: {len(result['files'])} files")
    for check in result.get('checks', []):
        lines.append(f"{check['check_id']}: {check['state']}; " + '; '.join(check['reasons']))
    lines.extend(result.get('issues', []))
    if result.get('changed_inputs'):
        lines.append('Changed inputs: ' + ', '.join(result['changed_inputs']))
    if result.get('required_reruns'):
        lines.append('Required reruns: ' + ', '.join(result['required_reruns']))
    if result.get('reason'):
        lines.append(result['reason'])
    if fmt == 'github':
        level = 'notice' if payload['exit_code'] == 0 else 'error'
        location = f'file={_escape_property(str(path))},line=1,' if path else ''
        return f'::{level} {location}title=TraceMantle::{_escape_data(terminal("; ".join(lines)))}'
    return '\n'.join(terminal(line) for line in lines)


def main(argv: list[str]) -> None:
    args = _parser().parse_args(argv)
    try:
        result, code, location = _run(args)
        payload = {'tool': 'TraceMantle', 'version': __version__, 'schema_version': 1,
                   'command': args.command, 'exit_code': code, 'result': result}
        output = render_product(payload, args.format, location)
        if args.output:
            bundle = getattr(args, 'bundle', None) or getattr(args, 'candidate', None)
            if bundle:
                outside_bundle(args.output, bundle)
            if args.command == "compare":
                outside_bundle(args.output, args.baseline)
            if args.output.exists():
                if read_bounded_bytes(args.output, max_bytes=len(output.encode()) + 1, what='Output', error_cls=EvidenceError) != (output + '\n').encode():
                    raise EvidenceError(f'Output {args.output} already exists with different contents. Choose another destination.')
            else:
                with args.output.open('x', encoding='utf-8') as stream:
                    stream.write(output + '\n')
        else:
            print(output)
    except (EvidenceError, LedgerError, OSError, RuntimeError) as exc:
        code = 2
        payload = {'tool': 'TraceMantle', 'version': __version__, 'schema_version': 1,
                   'command': args.command, 'exit_code': code,
                   'result': {'state': 'infrastructure-error', 'reason': str(exc)}}
        print(render_product(payload, args.format, None))
    sys.exit(code)
