"""Closed check scopes are trusted assertions, not inferred author intent."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_build_plan_product import NOW, _bundle, _policy, _record, _trusted_repository
from tracemantle.bundle import create_manifest, manifest_from_dict
from tracemantle.comparison import compare
from tracemantle.policy import load_trusted_policy
from tracemantle.storage import EvidenceError


def commit(root: Path) -> str:
    subprocess.run(['git', 'add', '.'], cwd=root, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=Tests', '-c', 'user.email=tests@example.invalid',
                    'commit', '-qm', 'Trusted scope fixture'], cwd=root, check=True, capture_output=True)
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


@pytest.fixture
def scoped(tmp_path):
    root = _bundle(tmp_path / 'skill')
    with (root / 'SKILL.md').open('a') as stream:
        stream.write('\nExample: `auth/login.py`.\n')
    baseline = create_manifest(root)
    record = replace(_record(root), model='none', model_revision='none', model_immutable=False,
                     environment=(('os', 'test-os'), ('python', 'test-python')))
    trust = tmp_path / 'trust'
    _trusted_repository(trust, record)
    config = trust / 'pyproject.toml'
    scope = {'schema_version': 1, 'inputs': ['SKILL.md', 'helper.py'],
             'rationale': 'This fixture checks only the named files; it does not interpret prose as executable input.',
             'assumptions': ['No external inputs; test runner and interpreter are pinned.'], 'unresolved': []}
    raw = json.dumps(scope).encode()
    (trust / 'scope.json').write_bytes(raw)
    profile = hashlib.sha256(raw).hexdigest()
    policy = load_trusted_policy(trust, subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=trust, text=True).strip())
    record = replace(record, profile_sha256=profile, checker_sha256=policy.checks[0].checker_sha256)
    text = config.read_text().replace('schema_version=1', 'schema_version=3').replace('kind="behavioral"', 'kind="deterministic"')
    import re
    text = re.sub(r'trusted_evidence=\[.*?\]', f'trusted_evidence=["{record.sha256}"]', text)
    text = re.sub(r'profile_sha256="[a-f0-9]+"', f'profile_sha256="{profile}"\ninput_scope_path="scope.json"', text)
    text = text.replace('context={permissions="read-bundle"}', 'context={runner="synthetic-test",adapter="test/v1",os="test-os",python="test-python"}')
    config.write_text(text)
    revision = commit(trust)
    return root, baseline, record, trust, revision


def test_unchanged_and_unrelated_reuse_with_visible_uncertainty(scoped):
    root, baseline, record, trust, revision = scoped
    policy = load_trusted_policy(trust, revision)
    assert not baseline.complete and baseline.issues
    for unrelated in (False, True):
        if unrelated:
            (root / 'notes.txt').write_text('Unrelated license review')
        result = compare(baseline, create_manifest(root), (record,), policy, now=NOW)
        assert result.state == 'pass' and result.checks[0].rerun is False
        assert result.issues
    assert manifest_from_dict(baseline.to_dict()) == baseline
    legacy = baseline.to_dict()
    legacy['schema_version'] = 1
    del legacy['resource_errors']
    assert compare(manifest_from_dict(legacy), baseline, (record,), policy, now=NOW).state == 'unknown'


@pytest.mark.parametrize('change', ['helper', 'documented-command', 'missing-link', 'escape', 'template', 'mode'])
def test_affected_inputs_and_explicit_errors_prevent_reuse(scoped, change):
    root, baseline, record, trust, revision = scoped
    if change == 'helper':
        (root / 'helper.py').write_text('changed executable behavior')
    elif change == 'mode':
        path = root / 'helper.py'
        original = path.stat().st_mode
        path.chmod(original ^ 0o111)
        if bool(path.stat().st_mode & 0o111) == bool(original & 0o111):
            pytest.skip('Platform cannot change executable bits')
    else:
        with (root / 'SKILL.md').open('a') as stream:
            stream.write({'documented-command': '\n```sh\nfalse\n```', 'missing-link': '\n[required](missing.py)',
                          'escape': '\n[required](../outside.py)', 'template': '\n[required]({baseDir}/../outside.py)'}[change])
    result = compare(baseline, create_manifest(root), (record,), load_trusted_policy(trust, revision), now=NOW)
    assert result.state == 'unknown' and result.checks[0].rerun


def test_declaration_cannot_conceal_preexisting_explicit_error(scoped):
    root, _, record, trust, revision = scoped
    with (root / 'SKILL.md').open('a') as stream:
        stream.write('\n[missing](missing.py)\n')
    broken = create_manifest(root)
    record = replace(record, bundle_sha256=broken.sha256, inputs=tuple((f.path, f.sha256) for f in broken.files))
    policy = load_trusted_policy(trust, revision)
    policy = replace(policy, trusted_evidence=frozenset({record.sha256}))
    assert broken.resource_errors
    assert compare(broken, broken, (record,), policy, now=NOW).state == 'unknown'


@pytest.mark.parametrize('fault', ['missing', 'expired', 'conflict', 'altered', 'unapproved', 'checker', 'config', 'environment', 'declaration'])
def test_scope_retains_evidence_requirements(scoped, fault):
    root, baseline, record, trust, revision = scoped
    policy = load_trusted_policy(trust, revision)
    records = (record,)
    if fault == 'missing':
        records = ()
    elif fault == 'expired':
        records = (replace(record, observed_at='2020-01-01T00:00:00Z'),)
        policy = replace(policy, trusted_evidence=frozenset({records[0].sha256}))
    elif fault == 'conflict':
        records += (replace(record, state='fail'),)
        policy = replace(policy, trusted_evidence=frozenset(r.sha256 for r in records))
    elif fault == 'altered':
        records = (replace(record, reason='altered after approval'),)
    elif fault == 'unapproved':
        policy = replace(policy, trusted_evidence=frozenset())
    else:
        field = {'checker': 'checker_sha256', 'config': 'configuration_sha256',
                 'environment': 'context', 'declaration': 'profile_sha256'}[fault]
        changed = (('python', 'different'),) if fault == 'environment' else 'f' * 64
        policy = replace(policy, checks=(replace(policy.checks[0], **{field: changed}),))
    assert compare(baseline, create_manifest(root), records, policy, now=NOW).checks[0].rerun


@pytest.mark.parametrize('fault', ['unresolved', 'omitted-input', 'mismatched-digest', 'behavioral', 'unknown-context', 'duplicate-json'])
def test_invalid_scope_rejected_from_trusted_git(scoped, fault):
    _, _, _, trust, _ = scoped
    path = trust / 'scope.json'
    scope = json.loads(path.read_bytes())
    if fault == 'unresolved':
        scope['unresolved'] = ['Runtime-selected network input']
    elif fault == 'omitted-input':
        scope['inputs'] = ['SKILL.md']
    if fault in {'unresolved', 'omitted-input'}:
        path.write_text(json.dumps(scope))
    elif fault == 'mismatched-digest':
        path.write_text(path.read_text() + '\n')
    elif fault == 'duplicate-json':
        path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
    else:
        config = trust / 'pyproject.toml'
        config.write_text(config.read_text().replace('kind="deterministic"', 'kind="behavioral"') if fault == 'behavioral'
                          else config.read_text().replace('test-python', 'unknown'))
    with pytest.raises(EvidenceError):
        load_trusted_policy(trust, commit(trust))


def test_candidate_cannot_replace_scope_or_policy(scoped):
    _, _, _, trust, revision = scoped
    before = load_trusted_policy(trust, revision)
    (trust / 'scope.json').write_text('{"inputs":[]}')
    (trust / 'pyproject.toml').write_text('[tool.tracemantle.release]\nchecks=[]')
    assert load_trusted_policy(trust, revision) == before


def test_legacy_incomplete_unchanged_remains_unknown(tmp_path):
    root = _bundle(tmp_path / 'skill')
    with (root / 'SKILL.md').open('a') as stream:
        stream.write('\n`auth/login.py`\n')
    record = _record(root)
    manifest = create_manifest(root)
    assert compare(manifest, manifest, (record,), _policy(record), now=NOW).state == 'unknown'


@pytest.mark.parametrize('change', ['shared-helper', 'first-checker', 'documentation'])
def test_scope_uncertainty_and_changes_are_per_check(scoped, change):
    root, baseline, record, trust, revision = scoped
    policy = load_trusted_policy(trust, revision)
    second_profile = hashlib.sha256(b'Independent synthetic helper-only scope').hexdigest()
    second_check = replace(policy.checks[0], id='helper-only', inputs=('helper.py',),
                           profile_sha256=second_profile, input_scope_sha256=second_profile)
    second_record = replace(record, check_id='helper-only', profile_sha256=second_profile, inputs=tuple((p, sha) for p, sha in record.inputs if p == 'helper.py'))
    policy = replace(policy, checks=(*policy.checks, second_check), trusted_evidence=frozenset({record.sha256, second_record.sha256}))
    if change == 'shared-helper':
        (root / 'helper.py').write_text('changed shared code')
    elif change == 'first-checker':
        policy = replace(policy, checks=(replace(policy.checks[0], checker_sha256='f' * 64), second_check))
    else:
        with (root / 'SKILL.md').open('a') as stream:
            stream.write('\nAnother ambiguous example: `elsewhere/input.txt`.\n')
    result = compare(baseline, create_manifest(root), (record, second_record), policy, now=NOW)
    assert result.checks[0].rerun
    assert result.checks[1].rerun == (change == 'shared-helper')
    assert result.state == 'unknown'


@pytest.mark.parametrize('field', ['model', 'model_revision'])
def test_deterministic_scope_cannot_relabel_model_execution(scoped, field):
    root, baseline, record, trust, revision = scoped
    policy = load_trusted_policy(trust, revision)
    # Even approved provenance cannot turn model execution into a non-model check.
    changed = 'hosted-model-alias'
    record = replace(record, **{field: changed})
    policy = replace(policy, trusted_evidence=frozenset({record.sha256}))
    assert compare(baseline, create_manifest(root), (record,), policy, now=NOW).checks[0].rerun
