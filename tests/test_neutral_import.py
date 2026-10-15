"""Data-only neutral imports use synthetic canonical observations."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_build_plan_product import _bundle, _record
from tracemantle.storage import canonical


def _import(source: Path, bundle: Path, store: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', 'import-evidence', str(source), '--input-format', 'neutral',
                           '--bundle', str(bundle), '--store', str(store), '--format', 'json', *extra], capture_output=True, text=True)


def test_neutral_import_preserves_source_unknowns_and_assigns_importer_identity(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    row = _record(bundle).to_dict() | {'observation_method': 'unknown', 'model': 'unknown', 'model_immutable': False,
                                     'reason': '__import__("os").system("must never execute")'}
    source = tmp_path / 'export.json'
    source.write_text(json.dumps({'schema_version': 1, 'records': [row]}, indent=2))
    result = _import(source, bundle, tmp_path / 'store')
    assert result.returncode == 4, result.stdout
    payload = json.loads(result.stdout)
    assert payload['schema_version'] == 1 and payload['result']['state'] == 'unknown'
    assert Path(payload['result']['source_copy']).read_bytes() == source.read_bytes()
    stored = json.loads(Path(payload['result']['records'][0]).read_bytes())
    assert stored == row | {'adapter': 'tracemantle/neutral-v1', 'artifact_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    assert _import(source, bundle, tmp_path / 'store').stdout == result.stdout


@pytest.mark.parametrize('case', ['overflow', 'duplicate', 'oversized', 'second-invalid', 'binding', 'wrong-bundle', 'version', 'empty', 'code', 'bad-source-identity'])
def test_invalid_neutral_imports_leave_no_partial_store(tmp_path: Path, case: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    row = _record(bundle).to_dict()
    source = tmp_path / 'export.json'
    data = {'schema_version': 1, 'records': [row]}
    extra = []
    if case == 'second-invalid':
        data['records'].append({'check_id': 'invalid'})
    elif case == 'binding':
        bindings = tmp_path / 'bindings.json'
        bindings.write_bytes(canonical({'schema_version': 1, 'rows': {'unwanted': row}}))
        extra = ['--bindings', str(bindings)]
    elif case == 'wrong-bundle':
        row['inputs']['helper.py'] = '0' * 64
    elif case == 'version':
        data['schema_version'] = True
    elif case == 'empty':
        data['records'] = []
    elif case == 'code':
        data['execute'] = f'open({str(tmp_path / "marker")!r}, "w")'
    elif case == 'bad-source-identity':
        row['artifact_sha256'] = 'not-a-digest'
    raw = canonical(data)
    if case == 'overflow':
        raw = raw.replace(b'"schema_version":1', b'"schema_version":1e999')
    elif case == 'duplicate':
        raw = raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1')
    elif case == 'oversized':
        raw = b' ' * (5 * 1024 * 1024 + 1)
    source.write_bytes(raw)
    result = _import(source, bundle, tmp_path / 'store', *extra)
    assert result.returncode == 2, result.stdout
    assert not (tmp_path / 'store').exists() and not (tmp_path / 'marker').exists()
