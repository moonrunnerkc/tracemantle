"""Authentic npm-generated exports; mutations below are synthetic negative controls."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_build_plan_product import _bundle, _record
from tracemantle.adapters.promptfoo import import_promptfoo
from tracemantle.storage import EvidenceError, canonical

ROOT = Path(__file__).parent / 'fixtures/upstream/promptfoo-0.124.1'


def test_fixture_bytes_match_recorded_provenance() -> None:
    provenance = json.loads((ROOT / 'PROVENANCE.json').read_bytes())
    for name, expected in provenance['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    assert provenance['export_version'] == '0.124.1' and provenance['results_schema_version'] == 3


@pytest.mark.parametrize('name,states', [('export.json', ['pass', 'fail']), ('error-export.json', ['infrastructure-error'])])
def test_actual_current_exports_import_through_cli(tmp_path: Path, name: str, states: list[str]) -> None:
    source = ROOT / name
    data = json.loads(source.read_bytes())
    bundle = _bundle(tmp_path / 'bundle')
    bindings = tmp_path / 'bindings.json'
    bindings.write_bytes(canonical({'schema_version': 1, 'rows': {r['id']: _record(bundle).to_dict() for r in data['results']['results']}}))
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'import-evidence', str(source), '--bundle', str(bundle),
                             '--bindings', str(bindings), '--store', str(tmp_path / 'store'), '--format', 'json'], capture_output=True, text=True)
    assert result.returncode == 4, result.stdout
    imported = json.loads(result.stdout)['result']
    records = [json.loads(Path(p).read_bytes()) for p in imported['records']]
    assert [r['state'] for r in records] == states
    assert all(r['adapter'] == 'promptfoo/0.124.1/results-v3/adapter-v1' and r['observation_method'] == 'unknown' for r in records)
    assert Path(imported['source_copy']).read_bytes() == source.read_bytes()


@pytest.mark.parametrize('case', ['version', 'schema', 'unknown-shape', 'missing-id', 'grading-conflict', 'grading-components',
                                  'failure-type', 'failure-conflict', 'token-usage', 'runtime', 'vars', 'overflow'])
def test_malformed_unbound_rows_and_unsupported_contracts_fail_without_writes(tmp_path: Path, case: str) -> None:
    data = json.loads((ROOT / 'export.json').read_bytes())
    row = data['results']['results'][1]
    if case == 'version':
        data['metadata']['promptfooVersion'] = '0.124.2'
    elif case == 'schema':
        data['results']['version'] = 4
    elif case == 'unknown-shape':
        data['traces'] = []
    elif case == 'missing-id':
        del row['id']
    elif case == 'grading-conflict':
        row['gradingResult']['pass'] = True
    elif case == 'grading-components':
        row['gradingResult']['componentResults'] = None
    elif case == 'failure-type':
        row['failureReason'] = True
    elif case == 'failure-conflict':
        data['results']['results'][0]['failureReason'] = 2
    elif case == 'token-usage':
        row['tokenUsage'] = []
    elif case == 'runtime':
        data['runtimeOptions'] = []
    elif case == 'vars':
        data['vars'] = [1]
    raw = canonical(data)
    if case == 'overflow':
        raw = raw.replace(b'"cost":0', b'"cost":1e999')
    source = tmp_path / 'source.json'
    source.write_bytes(raw)
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'import-evidence', str(source), '--bundle', str(_bundle(tmp_path / 'bundle')),
                             '--store', str(tmp_path / 'store'), '--format', 'json'], capture_output=True, text=True)
    assert result.returncode == 2, result.stdout
    assert not (tmp_path / 'store').exists()


def test_partial_grading_and_missing_model_identity_are_not_invented(tmp_path: Path) -> None:
    data = json.loads((ROOT / 'export.json').read_bytes())
    row = data['results']['results'][0]
    row['provider'] = {}
    # A threshold can pass overall even when a component fails. Do not infer the aggregate from components.
    row['gradingResult']['componentResults'][0]['pass'] = False
    bound = _record(_bundle(tmp_path / 'bundle')).to_dict()
    bindings = {'schema_version': 1, 'rows': {row['id']: bound}}
    record = import_promptfoo(canonical(data), bindings).records[0]
    assert record.state == 'pass' and record.model == 'unknown' and record.observation_method == 'unknown'
    row['success'] = False
    row['gradingResult']['pass'] = False
    assert import_promptfoo(canonical(data), bindings).records[0].state == 'unknown'
    row['failureReason'] = 2
    assert import_promptfoo(canonical(data), bindings).records[0].state == 'infrastructure-error'
    row['failureReason'] = 1
    row['gradingResult'] = None
    with pytest.raises(EvidenceError, match='missing assertion grading'):
        import_promptfoo(canonical(data), bindings)
