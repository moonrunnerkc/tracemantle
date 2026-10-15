"""Real signatures and temporary Git trust roots; synthetic observations only."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.test_build_plan_product import _bundle, _record, _trusted_repository
from tests.test_signatures import _ssh_key, _ssh_sign, needs_ssh
from tracemantle.approvals import approval_envelope, verify_approval
from tracemantle.evidence import evidence_from_dict
from tracemantle.policy import load_trusted_policy
from tracemantle.storage import EvidenceError, canonical

pytestmark = needs_ssh


def _commit(root: Path) -> str:
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Tests', '-c', 'user.email=tests@example.invalid',
                    'commit', '-qm', 'Change trusted authority'], check=True)
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


@pytest.fixture
def gate(tmp_path: Path) -> dict:
    private, public = _ssh_key(tmp_path / 'keys', 'owner')
    bundle = _bundle(tmp_path / 'bundle')
    now = datetime.now(timezone.utc)
    trust = tmp_path / 'trust'
    _trusted_repository(trust, replace(_record(bundle), observed_at=now.isoformat()))
    path = trust / 'approved.json'
    record = evidence_from_dict(json.loads(path.read_bytes()))
    config = trust / 'pyproject.toml'
    config.write_text(config.read_text().replace('schema_version=1', 'schema_version=2').replace(
        f'trusted_evidence=["{record.sha256}"]', 'trusted_evidence=[]\n[tool.tracemantle.release.automation]\n'
        f'signers=[{json.dumps(public)}]\nchecks=["validate"]\nmax_age_seconds=600'))
    revision = _commit(trust)
    policy = load_trusted_policy(trust, revision)
    start = (now - timedelta(seconds=1)).isoformat()
    envelope = approval_envelope(record, policy, run_id='protected/job/1', run_started_at=start,
                                 issued_at=now.isoformat(), expires_at=(now + timedelta(seconds=300)).isoformat())
    approval = path.with_name(path.name + '.approval.json')
    approval.write_bytes(canonical(envelope))
    _ssh_sign(private, approval)
    return dict(bundle=bundle, trust=trust, path=path, record=record, policy=policy, private=private,
                envelope=envelope, approval=approval, start=start, now=now)


def _compare(gate: dict, *extra: str, records: list[Path] | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, '-m', 'tracemantle', 'compare', str(gate['bundle']), str(gate['bundle']),
               '--trusted-root', str(gate['trust']), '--base-revision', gate['policy'].revision,
               '--approval-run-id', 'protected/job/1', '--approval-run-started-at', gate['start'], '--format', 'json']
    for path in records if records is not None else [gate['path']]:
        command.extend(['--evidence', str(path)])
    return subprocess.run([*command, *extra], capture_output=True, text=True)


def _resign(gate: dict) -> None:
    gate['approval'].write_bytes(canonical(gate['envelope']))
    gate['approval'].with_name(gate['approval'].name + '.sig').unlink(missing_ok=True)
    _ssh_sign(gate['private'], gate['approval'])


def test_automation_pass_and_disabled_authority_restore_digest_requirement(gate: dict) -> None:
    assert _compare(gate).returncode == 0
    config = gate['trust'] / 'pyproject.toml'
    original = config.read_text()
    head, tail = original.split('[tool.tracemantle.release.automation]')
    config.write_text(head + '[[tool.tracemantle.release.checks]]' + tail.split('[[tool.tracemantle.release.checks]]')[1])
    for version in (2, 1):
        config.write_text(config.read_text().replace('schema_version=2', f'schema_version={version}'))
        gate['policy'] = load_trusted_policy(gate['trust'], _commit(gate['trust']))
        result = _compare(gate)
        assert result.returncode == 4 and 'not approved' in result.stdout


@pytest.mark.parametrize('field,value', [('evidence_sha256', '0' * 64), ('bundle_sha256', '0' * 64),
    ('policy_sha256', '0' * 64), ('trusted_revision', '0' * 40), ('check_id', 'different'),
    ('run_id', 'other-run'), ('run_started_at', '2000-01-01T00:00:00Z'), ('schema_version', True),
    ('kind', 'check-evidence'), ('extra', 'unsupported')])
def test_wrong_signed_subject_or_run_fails_closed(gate: dict, field: str, value: object) -> None:
    gate['envelope'][field] = value
    _resign(gate)
    result = _compare(gate)
    assert result.returncode == 2 and json.loads(result.stdout)['result']['state'] == 'infrastructure-error'


@pytest.mark.parametrize('case', ['expired', 'future', 'too-long', 'before-start', 'replayed', 'missing-context'])
def test_approval_lifetime_and_independent_run_context(gate: dict, case: str) -> None:
    if case == 'expired':
        gate['envelope']['expires_at'] = gate['now'].isoformat()
    elif case == 'future':
        gate['envelope']['issued_at'] = (gate['now'] + timedelta(seconds=100)).isoformat()
    elif case == 'too-long':
        gate['envelope']['expires_at'] = (gate['now'] + timedelta(days=2)).isoformat()
    elif case == 'before-start':
        gate['start'] = (gate['now'] + timedelta(seconds=1)).isoformat()
        gate['envelope']['run_started_at'] = gate['start']
    _resign(gate)
    extra = ['--approval-run-id', 'protected/job/2'] if case == 'replayed' else ['--approval-run-id', ''] if case == 'missing-context' else []
    assert _compare(gate, *extra).returncode == 2


def test_wrong_key_altered_record_and_missing_signature(gate: dict, tmp_path: Path) -> None:
    sidecar = gate['approval'].with_name(gate['approval'].name + '.sig')
    sidecar.unlink()
    assert _compare(gate).returncode == 2
    stranger, _ = _ssh_key(tmp_path / 'stranger', 'key')
    _ssh_sign(stranger, gate['approval'])
    assert _compare(gate).returncode == 2
    _resign(gate)
    gate['path'].write_bytes(canonical(replace(gate['record'], reason='altered record').to_dict()))
    assert _compare(gate).returncode == 2


def test_revocation_and_missing_verifier(gate: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / 'no-tools'
    empty.mkdir()
    monkeypatch.setenv('PATH', str(empty))
    with pytest.raises(EvidenceError, match='ssh-keygen is not installed'):
        verify_approval(gate['record'], gate['path'], gate['policy'], candidate_sha256=gate['record'].bundle_sha256,
                        run_id='protected/job/1', run_started_at=gate['start'], now=gate['now'])
    monkeypatch.undo()
    _, public = _ssh_key(tmp_path / 'replacement', 'key')
    config = gate['trust'] / 'pyproject.toml'
    config.write_text(config.read_text().replace(json.dumps((tmp_path / 'keys/owner.pub').read_text().strip()), json.dumps(public)))
    gate['policy'] = load_trusted_policy(gate['trust'], _commit(gate['trust']))
    assert _compare(gate).returncode == 2
    # Even a new envelope naming the new base cannot make a removed key authoritative.
    gate['envelope'].update(policy_sha256=gate['policy'].sha256, trusted_revision=gate['policy'].revision)
    _resign(gate)
    assert _compare(gate).returncode == 2


@pytest.mark.parametrize('field,value', [('state', 'unknown'), ('state', 'skipped'), ('state', 'fail'),
    ('observation_method', 'model-judgment'), ('model_immutable', False), ('checker_sha256', '0' * 64),
    ('configuration_sha256', '0' * 64), ('profile_sha256', '0' * 64), ('fixture_sha256', '0' * 64),
    ('permissions', ('network',)), ('environment', ()), ('adapter', 'unknown')])
def test_approval_does_not_relax_evidence_compatibility(gate: dict, field: str, value: object) -> None:
    record = replace(gate['record'], **{field: value})
    gate['path'].write_bytes(canonical(record.to_dict()))
    gate['envelope']['evidence_sha256'] = record.sha256
    _resign(gate)
    result = _compare(gate)
    assert result.returncode == (1 if value == 'fail' else 4), result.stdout


def test_missing_conflicting_and_helper_changed_records_cannot_pass(gate: dict) -> None:
    assert _compare(gate, records=[]).returncode == 4
    failed = replace(gate['record'], state='fail')
    failure_path = gate['trust'] / 'failure.json'
    failure_path.write_bytes(canonical(failed.to_dict()))
    approval = failure_path.with_name(failure_path.name + '.approval.json')
    approval.write_bytes(canonical(gate['envelope'] | {'evidence_sha256': failed.sha256}))
    _ssh_sign(gate['private'], approval)
    assert _compare(gate, records=[gate['path'], failure_path]).returncode == 1
    (gate['bundle'] / 'helper.py').write_text('changed helper')
    assert _compare(gate).returncode == 2


def test_candidate_policy_checker_adapter_and_trust_worktree_cannot_choose_authority(gate: dict, tmp_path: Path) -> None:
    marker = tmp_path / 'executed'
    for name in ('checker.py', 'adapter.py', 'pyproject.toml'):
        (gate['trust'] / name).write_text(f'raise RuntimeError({str(marker)!r})')
    assert _compare(gate).returncode == 0
    assert not marker.exists()
    (gate['bundle'] / 'pyproject.toml').write_text('[tool.tracemantle.release]\nchecks=[]')
    (gate['bundle'] / 'adapter.py').write_text(f'open({str(marker)!r}, "w").write("executed")')
    assert _compare(gate).returncode == 2
    assert not marker.exists()


@pytest.mark.parametrize('change', ['version', 'empty-keys', 'bad-key', 'unknown-check', 'age', 'extra', 'schema1'])
def test_invalid_authority_configuration_fails_closed(gate: dict, change: str) -> None:
    config = gate['trust'] / 'pyproject.toml'
    value = config.read_text()
    if change == 'version':
        value = value.replace('schema_version=2', 'schema_version=3')
    elif change == 'schema1':
        value = value.replace('schema_version=2', 'schema_version=1')
    elif change in {'empty-keys', 'bad-key'}:
        start = value.index('signers=')
        end = value.index('\n', start)
        value = value[:start] + ('signers=[]' if change == 'empty-keys' else 'signers=["bad"]') + value[end:]
    elif change == 'unknown-check':
        value = value.replace('checks=["validate"]', 'checks=["not-listed"]')
    elif change == 'age':
        value = value.replace('max_age_seconds=600', 'max_age_seconds=true')
    else:
        value = value.replace('max_age_seconds=600', 'max_age_seconds=600\nallow_any=true')
    config.write_text(value)
    revision = _commit(gate['trust'])
    with pytest.raises(EvidenceError):
        load_trusted_policy(gate['trust'], revision)


@pytest.mark.parametrize('raw', [b'{"schema_version":1,"schema_version":1}', b'{"x":1e999}', b'x' * 65537])
def test_malformed_or_oversized_approval(gate: dict, raw: bytes) -> None:
    gate['approval'].write_bytes(raw)
    assert _compare(gate).returncode == 2


def test_required_record_signatures_still_apply_to_automation(gate: dict) -> None:
    config = gate['trust'] / 'pyproject.toml'
    public = gate['private'].with_suffix('.pub').read_text().strip()
    config.write_text(config.read_text().replace('trusted_evidence=[]', f'trusted_evidence=[]\nrequired_signers=[{json.dumps(public)}]'))
    gate['policy'] = load_trusted_policy(gate['trust'], _commit(gate['trust']))
    gate['envelope'].update(policy_sha256=gate['policy'].sha256, trusted_revision=gate['policy'].revision)
    _resign(gate)
    assert _compare(gate).returncode == 4
    _ssh_sign(gate['private'], gate['path'])
    assert _compare(gate).returncode == 0


@pytest.mark.skipif(sys.platform != 'linux' or not shutil.which('bwrap'), reason='Linux bubblewrap deployment example')
def test_producer_two_changed_bundles_no_digest_commits_and_secret_isolation(tmp_path: Path) -> None:
    probe = subprocess.run(['bwrap', '--unshare-all', '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
                            '--ro-bind', '/lib64', '/lib64', '/usr/bin/true'], capture_output=True)
    if probe.returncode:
        pytest.skip('Host disallows bubblewrap user namespaces')
    example = Path(__file__).resolve().parents[1] / 'docs/examples/protected_automation.py'
    root = tmp_path / 'demo'
    setup = subprocess.run([sys.executable, '-I', str(example), 'setup', str(root)], capture_output=True, text=True, check=True)
    revision = setup.stdout.strip()
    trust = root / 'trusted'
    policy_bytes = (trust / 'pyproject.toml').read_bytes()
    helper = root / 'candidate/demo/helper.py'
    records = []
    for run in (1, 2):
        # Candidate code is executed, but the signing key and host environment are absent.
        helper.write_text(f'import os, pathlib\nassert not pathlib.Path({str(root / "keys/approval")!r}).exists()\n'
                          f'assert "TRACEMANTLE_TEST_SECRET" not in os.environ\nprint("hello")\n# bundle {run}\n')
        started = datetime.now(timezone.utc).isoformat()
        produced = subprocess.run([sys.executable, '-I', str(trust / 'producer.py'), 'run', str(root),
                                   '--base-revision', revision, '--run-id', f'run-{run}', '--run-started-at', started],
                                  env=os.environ | {'TRACEMANTLE_TEST_SECRET': 'must-not-enter-sandbox'}, capture_output=True, text=True)
        assert produced.returncode == 0, produced.stderr
        record = Path(produced.stdout.strip())
        records.append(record)
        result = subprocess.run([sys.executable, '-m', 'tracemantle', 'compare', str(root / 'baseline/demo'), str(root / 'candidate/demo'),
                                 '--trusted-root', str(trust), '--base-revision', revision, '--evidence', str(record),
                                 '--approval-run-id', f'run-{run}', '--approval-run-started-at', started, '--format', 'json'],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)['result']['changed_inputs'] == ['helper.py']
    assert records[0] != records[1]
    assert (trust / 'pyproject.toml').read_bytes() == policy_bytes
    assert subprocess.check_output(['git', '-C', str(trust), 'rev-parse', 'HEAD'], text=True).strip() == revision
    helper.write_text('print("wrong greeting")\n')
    failed = subprocess.run([sys.executable, '-I', str(trust / 'producer.py'), 'run', str(root), '--base-revision', revision,
                             '--run-id', 'run-3', '--run-started-at', datetime.now(timezone.utc).isoformat()], capture_output=True, text=True)
    assert failed.returncode != 0 and 'Observer refuses approval' in failed.stderr
    assert len(list((root / 'store/records').glob('*.approval.json'))) == 2
