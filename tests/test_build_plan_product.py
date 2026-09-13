"""Synthetic gate tests; no test in this module claims a live agent execution."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tracemantle.bundle import create_manifest, manifest_from_dict, normalized_path
from tracemantle.comparison import compare
from tracemantle.core.history import LedgerError, load_ledger
from tracemantle.evidence import Evidence, evidence_from_dict
from tracemantle.history_store import migrate_legacy
from tracemantle.policy import RequiredCheck, TrustedPolicy, load_trusted_policy
from tracemantle.product_commands import render_product
from tracemantle.promptfoo import VERSION, import_promptfoo
from tracemantle.storage import EvidenceError, canonical, put_record

FIXTURES = Path(__file__).parent / 'fixtures'
CASES = FIXTURES / 'tracemantle/cases'
UPSTREAM = FIXTURES / 'upstream/promptfoo-0.118.10/sample-export.json'
NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
IDENTITY = 'a' * 64


def _bundle(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / 'SKILL.md').write_bytes((CASES / 'valid-standard.md').read_bytes() + b'\nRun [helper](helper.py).\n')
    (root / 'helper.py').write_text('print("synthetic helper")\n')
    return root


def _record(bundle: Path) -> Evidence:
    manifest = create_manifest(bundle)
    return Evidence('validate', 'pass', manifest.sha256, IDENTITY, IDENTITY, IDENTITY, IDENTITY, IDENTITY,
                    tuple((f.path, f.sha256) for f in manifest.files), '2026-09-12T11:59:00Z', 'observed-execution',
                    'synthetic-test', 'test/v1', 'test-model', 'revision-1', True, ('read-bundle',),
                    (('sandbox', 'isolated'),), (('backend', 'heuristic'),), 'Synthetic policy control, not a live evaluation.')


def _policy(record: Evidence, kind: str = 'behavioral') -> TrustedPolicy:
    check = RequiredCheck('validate', kind, ('SKILL.md', 'helper.py'), True, IDENTITY, IDENTITY, IDENTITY,
                          IDENTITY, 3600, True, (('permissions', 'read-bundle'),), ())
    return TrustedPolicy('1' * 40, (check,), frozenset({record.sha256}), IDENTITY)


@pytest.mark.parametrize('case', sorted(p.stem for p in CASES.glob('*.json')))
def test_conservative_comparison_scenarios(tmp_path: Path, case: str) -> None:
    scenario = json.loads((CASES / f'{case}.json').read_text())['scenario']
    base = _bundle(tmp_path / 'base')
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    record = _record(base)
    policy = _policy(record)
    expected = 'unknown'
    if scenario == 'control':
        expected = 'pass'
    elif scenario == 'helper-change':
        (candidate / 'helper.py').write_text('print("changed helper")\n')
    elif scenario == 'description-change':
        skill = candidate / 'SKILL.md'
        skill.write_text(skill.read_text().replace('Validates Python', 'Reviews Java'))
        policy = replace(policy, checks=(replace(policy.checks[0], kind='routing'),))
    elif scenario.startswith('wrong-'):
        field = {'bundle': 'bundle_sha256', 'checker': 'checker_sha256', 'profile': 'profile_sha256',
                 'fixture': 'fixture_sha256', 'config': 'configuration_sha256'}[scenario[6:]]
        record = replace(record, **{field: 'b' * 64})
    elif scenario == 'untrusted':
        policy = replace(policy, trusted_evidence=frozenset())
    elif scenario in {'stale', 'future'}:
        record = replace(record, observed_at='2020-01-01T00:00:00Z' if scenario == 'stale' else '2030-01-01T00:00:00Z')
    elif scenario == 'model-alias':
        # An unrelated new file permits static reuse, but an alias prevents behavioral reuse.
        (candidate / 'notes.txt').write_text('new notes')
        record = replace(record, model_immutable=False)
    elif scenario == 'inferred':
        record = replace(record, observation_method='inferred-trace')
    elif scenario == 'model-judgment':
        record = replace(record, observation_method='model-judgment')
    elif scenario == 'incomplete':
        (candidate / 'notes.txt').write_text('new notes')
        policy = replace(policy, checks=(replace(policy.checks[0], coverage_complete=False),))
    elif scenario in {'skipped', 'infrastructure', 'failed'}:
        state = {'skipped': 'skipped', 'infrastructure': 'infrastructure-error', 'failed': 'fail'}[scenario]
        record = replace(record, state=state)
        expected = 'unknown' if state == 'skipped' else state
    elif scenario == 'changed-permission':
        record = replace(record, permissions=('network',))
    if scenario != 'untrusted':
        policy = replace(policy, trusted_evidence=frozenset({record.sha256}))
    records = () if scenario == 'missing-evidence' else (record,)
    result = compare(create_manifest(base), create_manifest(candidate), records, policy, now=NOW)
    assert result.state == expected
    assert result.to_dict()['exit_code'] == result.exit_code
    assert result == compare(create_manifest(base), create_manifest(candidate), tuple(reversed(records)), policy, now=NOW)


def test_manifest_helper_identity_and_reproducibility(tmp_path: Path) -> None:
    base = _bundle(tmp_path / 'base')
    manifest = create_manifest(base)
    assert manifest_from_dict(manifest.to_dict()) == manifest
    assert manifest == create_manifest(base)
    (base / 'helper.py').write_text('changed')
    assert create_manifest(base).sha256 != manifest.sha256
    invalid = manifest.to_dict()
    invalid['files'][0]['size'] = True
    with pytest.raises(EvidenceError):
        manifest_from_dict(invalid)
    invalid = manifest.to_dict()
    invalid['bundle_sha256'] = '0' * 64
    with pytest.raises(EvidenceError):
        manifest_from_dict(invalid)


@pytest.mark.parametrize('path', ['/absolute', '../escape', 'a//b', 'a/./b', 'a\\b', 'C:drive', 'a\x1b.md', 'cafe\u0301.md'])
def test_ambiguous_manifest_paths_are_rejected(path: str) -> None:
    with pytest.raises(EvidenceError):
        normalized_path(path)


def test_manifest_does_not_follow_symlinks(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    try:
        (bundle / 'cycle').symlink_to(bundle, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'OS does not permit symlinks: {exc}')
    manifest = create_manifest(bundle)
    assert not manifest.complete
    assert any('symlink' in issue for issue in manifest.issues)


@pytest.mark.parametrize('field,value', [('schema_version', True), ('state', 'success'), ('bundle_sha256', 'short'),
    ('model_immutable', 'false'), ('observed_at', 'yesterday'), ('permissions', ['secret-key']),
    ('environment', {'API_KEY': 'secret'}), ('inputs', {'../escape': IDENTITY}), ('tokenizer', []), ('runner', '')])
def test_evidence_rejects_incomplete_and_coerced_identity(tmp_path: Path, field: str, value: object) -> None:
    data = _record(_bundle(tmp_path / 'bundle')).to_dict()
    data[field] = value
    with pytest.raises(EvidenceError):
        evidence_from_dict(data)


def test_promptfoo_authentic_fixture_is_version_pinned_and_does_not_claim_invocation(tmp_path: Path) -> None:
    raw = UPSTREAM.read_bytes()
    original = json.loads(raw)
    assert original['metadata']['promptfooVersion'] == VERSION
    record = _record(_bundle(tmp_path / 'bundle'))
    bindings = {'schema_version': 1, 'rows': {row['id']: record.to_dict() for row in original['results']['results']}}
    imported = import_promptfoo(raw, bindings)
    assert len(imported.records) == 4
    assert all(r.state == 'fail' and r.observation_method == 'model-judgment' for r in imported.records)
    assert imported.artifact_sha256 == hashlib.sha256(raw).hexdigest()
    assert import_promptfoo(raw, {'schema_version': 1, 'rows': {}}).issues
    original['metadata']['promptfooVersion'] = '0.0.0'
    with pytest.raises(EvidenceError, match='version'):
        import_promptfoo(canonical(original), bindings)


@pytest.mark.parametrize('field,value', [('success', 'false'), ('success', 1), ('testCase', []), ('provider', 'claimed'), ('gradingResult', {'pass': 'false'})])
def test_promptfoo_malformed_rows_are_rejected(field: str, value: object) -> None:
    data = json.loads(UPSTREAM.read_bytes())
    data['results']['results'][0][field] = value
    with pytest.raises(EvidenceError):
        import_promptfoo(canonical(data), {'schema_version': 1, 'rows': {}})


@pytest.mark.parametrize('section,field,value', [('result', 'valid', 'false'), ('result', 'error', True),
    ('validation_modes', 'symbolic', 'false'), ('result', 'info', -1), ('agents', 'graph_agent', 1)])
def test_legacy_history_fields_are_strict(tmp_path: Path, section: str, field: str, value: object) -> None:
    data = json.loads((FIXTURES / 'history/ledger_one_run.json').read_bytes())
    data['runs'][0][section][field] = value
    source = tmp_path / 'ledger.json'
    source.write_bytes(canonical(data))
    with pytest.raises(LedgerError):
        load_ledger(source)


def test_migration_is_explicit_idempotent_and_preserves_source(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    source = bundle / '.skillcheck-history.json'
    source.write_bytes((FIXTURES / 'history/ledger_one_run.json').read_bytes())
    before = source.read_bytes()
    store = tmp_path / 'store'
    first = migrate_legacy(source, store)
    second = migrate_legacy(source, store)
    assert first == second
    assert source.read_bytes() == before
    assert len(list((store / 'records').glob('*.json'))) == 1
    with pytest.raises(EvidenceError):
        migrate_legacy(source, bundle / 'inside')


def test_concurrent_immutable_writers_preserve_records(tmp_path: Path) -> None:
    command = 'import sys; from pathlib import Path; from tracemantle.storage import put_record; put_record(Path(sys.argv[1]), {"writer":sys.argv[2]})'
    processes = [subprocess.Popen([sys.executable, '-c', command, str(tmp_path), str(i)]) for i in range(8)]
    assert all(p.wait(timeout=20) == 0 for p in processes)
    assert len(list(tmp_path.glob('*.json'))) == 8
    assert not list(tmp_path.glob('.pending-*'))
    put_record(tmp_path, {'writer': '0'})
    assert len(list(tmp_path.glob('*.json'))) == 8


def _trusted_repository(root: Path, record: Evidence) -> str:
    root.mkdir()
    checker = b'print("trusted checker identity, never executed during comparison")\n'
    (root / 'checker.py').write_bytes(checker)
    checker_sha = hashlib.sha256(checker).hexdigest()
    record = replace(record, checker_sha256=checker_sha)
    (root / 'approved.json').write_bytes(canonical(record.to_dict()))
    config = f'''[tool.tracemantle.release]
schema_version=1
trusted_evidence=["{record.sha256}"]
[[tool.tracemantle.release.checks]]
id="validate"
kind="behavioral"
inputs=["SKILL.md", "helper.py"]
coverage_complete=true
checker_path="checker.py"
checker_sha256="{checker_sha}"
configuration_sha256="{IDENTITY}"
fixture_sha256="{IDENTITY}"
profile_sha256="{IDENTITY}"
max_age_seconds=31536000
required=true
routing_neighbors=[]
context={{permissions="read-bundle"}}
'''
    (root / 'pyproject.toml').write_text(config)
    for args in [['init', '-q'], ['add', '.'], ['-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid', 'commit', '-qm', 'Synthetic trusted policy fixture']]:
        subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


def test_cli_trusted_base_cannot_be_weakened_by_candidate(tmp_path: Path) -> None:
    base = _bundle(tmp_path / 'base')
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    trust = tmp_path / 'trust'
    record = replace(_record(base), observed_at=datetime.now(timezone.utc).isoformat())
    revision = _trusted_repository(trust, record)
    policy = load_trusted_policy(trust, revision)
    assert policy.revision == revision
    # Candidate attempts to remove checks or replace checker code are data.
    marker = tmp_path / 'candidate-executed'
    (candidate / 'pyproject.toml').write_text('[tool.tracemantle.release]\nchecks=[]\n')
    (candidate / 'checker.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n')
    # Working-tree replacement cannot alter the immutable Git policy/checker.
    (trust / 'pyproject.toml').write_text('[tool.tracemantle.release]\nchecks=[]\n')
    (trust / 'checker.py').write_text('candidate checker')
    command = [sys.executable, '-m', 'tracemantle', 'compare', str(base), str(candidate), '--trusted-root', str(trust), '--base-revision', revision, '--evidence', str(trust / 'approved.json'), '--format', 'json']
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['result']['state'] == 'pass'
    assert not marker.exists()
    (candidate / 'helper.py').write_text('changed')
    changed = subprocess.run(command, capture_output=True, text=True)
    assert changed.returncode == 4
    assert 'helper.py' in json.loads(changed.stdout)['result']['changed_inputs']
    missing = subprocess.run(command[:-4] + ['--format', 'json'], capture_output=True, text=True)
    assert missing.returncode == 4
    with pytest.raises(EvidenceError, match='40-character'):
        load_trusted_policy(trust, 'main')


def test_product_cli_manifest_import_migration_and_annotations(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    manifest = subprocess.run([sys.executable, '-m', 'tracemantle', 'manifest', str(bundle), '--format', 'json'], capture_output=True, text=True)
    assert manifest.returncode == 0
    assert json.loads(manifest.stdout)['result']['bundle_sha256'] == create_manifest(bundle).sha256
    imported = subprocess.run([sys.executable, '-m', 'tracemantle', 'import-evidence', str(UPSTREAM), '--bundle', str(bundle), '--store', str(tmp_path / 'store'), '--format', 'json'], capture_output=True, text=True)
    assert imported.returncode == 4
    data = json.loads(imported.stdout)
    assert Path(data['result']['source_copy']).read_bytes() == UPSTREAM.read_bytes()
    payload = {'command': 'compare', 'exit_code': 4, 'result': {'state': 'unknown', 'reason': '\x1b[2J'}}
    annotation = render_product(payload, 'github', bundle / 'SKILL.md')
    assert annotation.startswith('::error file=') and 'line=1' in annotation and '\x1b' not in annotation
