"""Adapter contract and the opt-in external adapter. Records here are synthetic."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_build_plan_product import UPSTREAM, _bundle, _record
from tracemantle import promptfoo as legacy_promptfoo
from tracemantle.adapters import CheckEvidence, adapt_external
from tracemantle.adapters import promptfoo as builtin
from tracemantle.evidence import Evidence
from tracemantle.storage import EvidenceError, canonical

ROW_ADAPTER = '''\
from tracemantle.adapters import evidence_from_dict
from tracemantle.storage import decode_json


def adapt(export_bytes, bindings):
    return [evidence_from_dict(row) for row in decode_json(export_bytes)]
'''


def _import(tmp_path: Path, adapter: Path, export: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', 'import-evidence', str(export), '--bundle', str(bundle),
                           '--store', str(tmp_path / 'store'), '--adapter', str(adapter), '--format', 'json'],
                          capture_output=True, text=True)


def _export(tmp_path: Path, bundle: Path) -> Path:
    export = tmp_path / 'export.json'
    export.write_bytes(canonical([_record(bundle).to_dict()]))
    return export


def test_builtin_adapter_returns_the_records_of_the_pinned_importer(tmp_path: Path) -> None:
    raw = UPSTREAM.read_bytes()
    record = _record(_bundle(tmp_path / 'bundle'))
    rows = json.loads(raw)['results']['results']
    bindings = {'schema_version': 1, 'rows': {rows[0]['id']: record.to_dict()}}
    adapted = builtin.adapt(raw, bindings)
    assert [r.adapter for r in adapted] == ['promptfoo/0.118.10/results-v3/adapter-v1']
    assert adapted == list(builtin.import_promptfoo(raw, bindings).records)
    assert builtin.adapt(raw, {'schema_version': 1, 'rows': {}}) == []
    assert CheckEvidence is Evidence


def test_legacy_promptfoo_import_path_still_resolves() -> None:
    assert legacy_promptfoo.import_promptfoo is builtin.import_promptfoo
    assert legacy_promptfoo.VERSION == '0.118.10'


def test_external_adapter_records_are_stored_under_the_adapter_file_identity(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    export = _export(tmp_path, bundle)
    adapter = tmp_path / 'row_adapter.py'
    adapter.write_text(ROW_ADAPTER)
    result = _import(tmp_path, adapter, export, bundle)
    assert result.returncode == 4, result.stdout + result.stderr
    payload = json.loads(result.stdout)['result']
    assert Path(payload['source_copy']).read_bytes() == export.read_bytes()
    stored = json.loads(Path(payload['records'][0]).read_bytes())
    # The synthetic record claimed adapter 'test/v1' and an unrelated artifact digest.
    assert stored['adapter'] == 'external/sha256:' + hashlib.sha256(adapter.read_bytes()).hexdigest()
    assert stored['artifact_sha256'] == hashlib.sha256(export.read_bytes()).hexdigest() == payload['artifact_sha256']
    assert stored['check_id'] == 'validate' and stored['observation_method'] == 'observed-execution'


@pytest.mark.parametrize('source,message', [
    ('VALUE = 1\n', 'must define adapt'),
    ('def adapt(export_bytes, bindings):\n    return [{"check_id": "validate"}]\n', 'must return a list'),
    ('def adapt(export_bytes, bindings):\n    raise RuntimeError("upstream format changed")\n', 'RuntimeError: upstream format changed'),
    ('def adapt(export_bytes, bindings:\n', 'SyntaxError'),
])
def test_broken_external_adapter_fails_the_import_without_writing_a_store(tmp_path: Path, source: str, message: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    adapter = tmp_path / 'broken.py'
    adapter.write_text(source)
    result = _import(tmp_path, adapter, _export(tmp_path, bundle), bundle)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload['result']['state'] == 'infrastructure-error' and message in payload['result']['reason']
    assert not (tmp_path / 'store').exists()


def test_adapter_inside_the_bundle_is_refused_before_it_runs(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    marker = tmp_path / 'bundle-code-ran'
    adapter = bundle / 'adapter.py'
    adapter.write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n' + ROW_ADAPTER)
    result = _import(tmp_path, adapter, _export(tmp_path, bundle), bundle)
    assert result.returncode == 2
    assert 'inside the evaluated bundle' in json.loads(result.stdout)['result']['reason']
    assert not marker.exists()


def test_external_adapter_record_for_another_bundle_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    other = _bundle(tmp_path / 'other')
    (other / 'helper.py').write_text('print("different helper")\n')
    adapter = tmp_path / 'row_adapter.py'
    adapter.write_text(ROW_ADAPTER)
    result = _import(tmp_path, adapter, _export(tmp_path, other), bundle)
    assert result.returncode == 2
    assert 'does not match the actual bundle' in json.loads(result.stdout)['result']['reason']
    assert not (tmp_path / 'store').exists()


def test_external_adapter_cannot_return_unvalidated_evidence(tmp_path: Path) -> None:
    adapter = tmp_path / 'direct.py'
    adapter.write_text('from tracemantle.evidence import Evidence\n\n\ndef adapt(export_bytes, bindings):\n'
                       '    return [Evidence(*["validate", "success"] + ["x"] * 18)]\n')
    with pytest.raises(EvidenceError):
        adapt_external(adapter, b'[]', {})
