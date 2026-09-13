"""Post-release audit regressions. Evidence records are synthetic policy controls."""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_build_plan_acceptance import _cli
from tests.test_build_plan_product import NOW, UPSTREAM, _bundle, _policy, _record
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.config_loader import ConfigError, project_configs
from tracemantle.core.history import ledger_path_for
from tracemantle.markdown import tokenize
from tracemantle.promptfoo import import_promptfoo
from tracemantle.storage import EvidenceError, canonical


@pytest.mark.parametrize('changed', [False, True])
@pytest.mark.parametrize('field,value,reason', [
    ('model_immutable', False, 'immutable'),
    ('runner', '  UNKNOWN  ', 'incomplete'),
    ('adapter', '   ', 'incomplete'),
    ('model_revision', ' Unknown ', 'incomplete'),
    ('environment', (('sandbox', 'unknown'),), 'incomplete'),
    ('environment', (('sandbox', ''),), 'incomplete'),
    ('tokenizer', (('backend', 'unknown'),), 'incomplete'),
    ('tokenizer', (('backend', '  '),), 'incomplete'),
])
def test_behavioral_reuse_checks_identity_even_for_equal_bundles(tmp_path: Path, changed: bool, field: str, value: object, reason: str) -> None:
    base = _bundle(tmp_path / 'base')
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    record = replace(_record(base), **{field: value})
    if field == 'model_immutable':
        record = replace(record, model='hosted-latest', model_revision='hosted-latest')
    if changed:
        (candidate / 'notes.txt').write_text('Unrelated notes')
    report = compare(create_manifest(base), create_manifest(candidate), (record,), _policy(record), now=NOW)
    assert report.state == 'unknown' and report.exit_code == 4
    assert report.checks[0].rerun
    assert reason in ' '.join(report.checks[0].reasons)


@pytest.mark.parametrize('kind', ['static', 'behavioral'])
@pytest.mark.parametrize('changed', [False, True])
def test_compatible_reuse_positive_controls(tmp_path: Path, kind: str, changed: bool) -> None:
    base = _bundle(tmp_path / 'base')
    before = create_manifest(base)
    record = _record(base)
    if kind == 'static':
        record = replace(record, observation_method='static-analysis', model='unknown', model_revision='unknown', model_immutable=False, environment=(), tokenizer=())
    if changed:
        (base / 'notes.txt').write_text('Unrelated notes')
    report = compare(before, create_manifest(base), (record,), _policy(record, kind), now=NOW)
    assert report.state == 'pass' and report.exit_code == 0


@pytest.mark.parametrize('field,value', [
    ('componentResults', None), ('componentResults', 1), ('componentResults', 'bad'),
    ('componentResults', {}), ('componentResults', [None]), ('componentResults', [1]),
    ('assertion', None), ('assertion', []), ('assertion', 1), ('assertion', 'bad'),
    ('assertion', {'type': []}), ('assertion', {'type': None}),
])
def test_promptfoo_nested_shapes_fail_with_bound_authentic_rows(tmp_path: Path, field: str, value: object) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    data = json.loads(UPSTREAM.read_bytes())
    grading = data['results']['results'][0]['gradingResult']
    if field == 'componentResults':
        grading[field] = value
    else:
        grading['componentResults'][0][field] = value
    bindings = {'schema_version': 1, 'rows': {row['id']: _record(bundle).to_dict() for row in data['results']['results']}}
    with pytest.raises(EvidenceError, match='componentResults|assertion'):
        import_promptfoo(canonical(data), bindings)
    with pytest.raises(EvidenceError, match='componentResults|assertion'):
        import_promptfoo(canonical(data), {'schema_version': 1, 'rows': {}})
    source, bound = tmp_path / 'export.json', tmp_path / 'bindings.json'
    source.write_bytes(canonical(data))
    bound.write_bytes(canonical(bindings))
    result = _cli('import-evidence', str(source), '--bundle', str(bundle), '--bindings', str(bound), '--store', str(tmp_path / 'store'), '--format', 'json')
    assert result.returncode == 2 and 'Traceback' not in result.stderr
    report = json.loads(result.stdout)
    assert report['result']['state'] == 'infrastructure-error'
    assert len(result.stdout) < 2000
    assert not (tmp_path / 'store').exists()


@pytest.mark.parametrize('value', ['1', '[]', '"tracemantle"'])
def test_auto_discovered_tool_must_be_table(tmp_path: Path, value: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    (bundle / 'pyproject.toml').write_text(f'tool = {value}\n')
    with pytest.raises(ConfigError, match='tool.*table'):
        project_configs(bundle)
    result = _cli(str(bundle), '--format', 'json')
    assert result.returncode == 2 and 'Traceback' not in result.stderr
    report = json.loads(result.stdout)
    assert report['schema_version'] == 2 and not report['gate']['passed']
    assert 'tool' in report['errors'][0]['error']


@pytest.mark.parametrize('value', ['2026-09-12', '2026-09-12T12:00:00Z', '[text]', '{key: text}', 'true', '42'])
@pytest.mark.parametrize('fmt', ['json', 'text', 'github'])
def test_manifest_invalid_description_is_domain_error(tmp_path: Path, value: str, fmt: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    (bundle / 'SKILL.md').write_text(f'---\nname: control\ndescription: {value}\n---\nBody.\n')
    with pytest.raises(EvidenceError, match='description.*string'):
        create_manifest(bundle)
    result = _cli('manifest', str(bundle), '--format', fmt)
    assert result.returncode == 2
    assert 'description' in result.stdout and 'Traceback' not in result.stderr
    if fmt == 'json':
        assert json.loads(result.stdout)['result']['state'] == 'infrastructure-error'


@pytest.mark.parametrize('no_color', [False, True])
@pytest.mark.parametrize('branch', ['missing', 'empty-store', 'multiple'])
def test_history_paths_escape_controls(tmp_path: Path, no_color: bool, branch: str) -> None:
    if sys.platform == 'win32':
        pytest.skip('Windows filenames cannot contain ESC; display function coverage runs separately.')
    bundle = _bundle(tmp_path / 'café\x1b[2J')
    if branch == 'empty-store':
        ledger_path_for(bundle / 'SKILL.md').mkdir(parents=True)
    paths = [str(bundle)]
    if branch == 'multiple':
        paths.insert(0, str(_bundle(tmp_path / 'ordinary')))
    result = _cli(*paths, '--show-history', *(['--no-color'] if no_color else []))
    assert result.returncode == (0 if branch == 'empty-store' else 2)
    assert '\x1b' not in result.stdout + result.stderr
    if branch != 'empty-store':
        assert 'café\\x1b[2J' in result.stderr


@pytest.mark.parametrize('example', [
    '`[label](missing.md)`', '``[label](missing.md)``', '`` `[label](missing.md)` ``',
    '`[label](scripts/missing.md)`', '`[label/path]`', '`include:scripts/missing.md`',
    '`![label](missing.png)`', '`<a href="missing.md">`', '`include: missing.md`',
    '`[label]: missing.md`\n[label]', '    [label](missing.md)', '\t[label](missing.md)',
    '    [label]: missing.md\n\n[label]', '    <img src="missing.png">',
    '    include: missing.md', '```md\n[label](missing.md)\n```',
    '~~~~\n[label](missing.md)\n~~~~', '``multi\n[label](missing.md)\nline``',
])
def test_markdown_code_examples_are_not_dependencies(example: str) -> None:
    markdown = tokenize(example, 8)
    assert markdown.resources == ()
    assert not markdown.uncertain


@pytest.mark.parametrize('body,target,kind,line', [
    ('`scripts/helper.py`', 'scripts/helper.py', 'resource', 8),
    ('`assets(v1)/helper.py`', 'assets(v1)/helper.py', 'resource', 8),
    ('`scripts/helper[old].py`', 'scripts/helper[old].py', 'resource', 8),
    ('``scripts/helper.py``', 'scripts/helper.py', 'resource', 8),
    ('`report.json`', 'report.json', 'generated', 8),
    ('`example` [real](actual.md)', 'actual.md', 'link', 8),
    ('`` a ` b ``\n[real](actual.md)', 'actual.md', 'link', 9),
    ('`unclosed [real](actual.md)', 'actual.md', 'link', 8),
    ('`unclosed\n\n[real](actual.md) `', 'actual.md', 'link', 10),
    ('`unclosed\n```\nexample\n```\n[real](actual.md) `', 'actual.md', 'link', 12),
    ('[label]: actual.md\n[label]', 'actual.md', 'link', 8),
    ('    [example](missing.md)\n\n[real](actual.md)', 'actual.md', 'link', 10),
])
def test_markdown_real_resources_keep_locations(body: str, target: str, kind: str, line: int) -> None:
    resources = tokenize(body, 8).resources
    assert [(r.target, r.kind, r.line) for r in resources] == [(target, kind, line)]


@pytest.mark.parametrize('state,expected,code', [('fail', 'fail', 1), ('unknown', 'unknown', 4), ('skipped', 'unknown', 4), ('infrastructure-error', 'infrastructure-error', 2)])
def test_conflicting_approved_records_cannot_hide_nonpassing_state(tmp_path: Path, state: str, expected: str, code: int) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    manifest = create_manifest(bundle)
    passing = _record(bundle)
    other = replace(passing, state=state)
    policy = replace(_policy(passing), trusted_evidence=frozenset({passing.sha256, other.sha256}))
    for records in ((passing, other), (other, passing)):
        report = compare(manifest, manifest, records, policy, now=NOW)
        assert report.state == expected and report.exit_code == code
        assert report.checks[0].rerun


def test_nonpublishing_workflow_preserves_real_release_dependency() -> None:
    import yaml
    root = Path(__file__).resolve().parents[1]
    release = yaml.safe_load((root / '.github/workflows/release.yml').read_text())
    guard = yaml.safe_load((root / '.github/workflows/verify-gates.yml').read_text())
    workflow = yaml.safe_load((root / '.github/workflows/compare.yml').read_text())
    steps = workflow['jobs']['compare']['steps']
    installs = [step['run'] for step in steps if 'run' in step and 'pip install' in step['run']]
    assert installs == ['pip install -c trusted/constraints-dev.txt ./trusted']
    assert workflow['permissions'] == {'contents': 'read'}
    assert steps[0]['with']['ref'] == '${{ inputs.base_revision }}'
    assert steps[0]['with']['persist-credentials'] is False
    assert steps[1]['with']['persist-credentials'] is False
    assert release['jobs']['release']['needs'] == guard['jobs']['publishing-sentinel']['needs'] == 'quality'
    assert release['jobs']['quality']['uses'] == './.github/workflows/ci.yml'
    assert release['jobs']['release']['if'] == "vars.TRACEMANTLE_PUBLISH_ENABLED == 'true'"
    assert release['jobs']['move-major-tag']['needs'] == 'release'
    assert guard['permissions'] == {'contents': 'read'}
    assert set(guard.get('on', guard.get(True))) == {'workflow_dispatch'}
    assert all('environment' not in job for job in guard['jobs'].values())
    assert all('pypi' not in str(step).lower() for job in guard['jobs'].values() for step in job['steps'])


def test_history_missing_after_discovery_escapes_path(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import argparse

    import tracemantle.commands as commands
    source = tmp_path / 'café\x1b[2J.md'
    ledger = ledger_path_for(source)
    ledger.mkdir(parents=True)
    original_load = commands.load_ledger

    def removed_before_read(path: Path):
        path.rmdir()
        return original_load(path)

    monkeypatch.setattr(commands, 'load_ledger', removed_before_read)
    with pytest.raises(SystemExit) as exited:
        commands.run_show_history(argparse.Namespace(quiet=False, format='text'), [source])
    assert exited.value.code == 2
    captured = capsys.readouterr()
    assert '\x1b' not in captured.out + captured.err
    assert 'café\\x1b[2J' in captured.err


def test_markdown_code_contexts_through_cli_and_manifest(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    source = bundle / 'SKILL.md'
    source.write_text(source.read_text() + '\n`[example](missing.md)`\n\n    include: absent.md\n')
    result = _cli(str(bundle), '--skip-dirname-check', '--format', 'json')
    assert result.returncode == 0 and json.loads(result.stdout)['gate']['passed']
    assert create_manifest(bundle).complete
    source.write_text(source.read_text() + '\n[real](missing.md)\n')
    result = _cli(str(bundle), '--skip-dirname-check', '--format', 'json')
    assert result.returncode == 1 and 'references.broken' in result.stdout
    assert not create_manifest(bundle).complete


@pytest.mark.parametrize('defect', ['alias', 'environment', 'tokenizer'])
@pytest.mark.parametrize('changed', [False, True])
def test_incompatible_approved_behavioral_evidence_blocks_real_cli(tmp_path: Path, defect: str, changed: bool) -> None:
    from datetime import datetime, timezone

    from tests.test_build_plan_product import _trusted_repository
    base = _bundle(tmp_path / 'base')
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    record = replace(_record(base), observed_at=datetime.now(timezone.utc).isoformat())
    if defect == 'alias':
        record = replace(record, model='hosted-latest', model_revision='hosted-latest', model_immutable=False)
    elif defect == 'environment':
        record = replace(record, environment=(('sandbox', 'unknown'),))
    else:
        record = replace(record, tokenizer=(('backend', 'unknown'),))
    trusted = tmp_path / 'trusted'
    revision = _trusted_repository(trusted, record)
    if changed:
        (candidate / 'notes.txt').write_text('Unrelated note')
    result = _cli('compare', str(base), str(candidate), '--trusted-root', str(trusted), '--base-revision', revision, '--evidence', str(trusted / 'approved.json'), '--format', 'json')
    report = json.loads(result.stdout)
    assert result.returncode == report['exit_code'] == 4
    assert report['result']['state'] == 'unknown'
    assert report['result']['required_reruns'] == ['validate']


def test_malformed_trusted_check_kind_is_domain_error(tmp_path: Path) -> None:
    import subprocess

    from tests.test_build_plan_product import _trusted_repository
    from tracemantle.policy import load_trusted_policy
    bundle = _bundle(tmp_path / 'bundle')
    trusted = tmp_path / 'trusted'
    _trusted_repository(trusted, _record(bundle))
    path = trusted / 'pyproject.toml'
    path.write_text(path.read_text().replace('kind="behavioral"', 'kind=[]'))
    subprocess.run(['git', '-C', str(trusted), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(trusted), '-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid', 'commit', '-qm', 'Malformed synthetic policy'], check=True)
    revision = subprocess.check_output(['git', '-C', str(trusted), 'rev-parse', 'HEAD'], text=True).strip()
    with pytest.raises(EvidenceError, match='kind'):
        load_trusted_policy(trusted, revision)
    result = _cli('compare', str(bundle), str(bundle), '--trusted-root', str(trusted), '--base-revision', revision, '--format', 'json')
    assert result.returncode == 2 and json.loads(result.stdout)['result']['state'] == 'infrastructure-error'


@pytest.mark.parametrize('scalar', [
    pytest.param('2026-99-12', id='invalid-month'),
    pytest.param('2026-09-12T25:00:00Z', id='invalid-hour'),
    pytest.param('2026-09-12T12:00:00+25:00', id='invalid-timezone'),
    pytest.param('9' * 5000, id='integer-conversion-limit'),
])
def test_yaml_scalar_conversion_errors_are_bounded_and_batch_continues(tmp_path: Path, scalar: str) -> None:
    import os
    bad = _bundle(tmp_path / 'bad')
    (bad / 'SKILL.md').write_text(f'---\nname: control\ndescription: {scalar}\n---\nBody.\n')
    good = _bundle(tmp_path / 'good')
    environment = {**os.environ, 'PYTHONINTMAXSTRDIGITS': '4300'}
    result = _cli(str(bad), str(good), '--skip-dirname-check', '--format', 'json', env=environment)
    assert result.returncode == 1 and 'Traceback' not in result.stderr
    report = json.loads(result.stdout)
    assert len(report['results']) == 2
    assert sum(item['valid'] for item in report['results']) == 1
    diagnostic = next(d for item in report['results'] for d in item['diagnostics'] if d['rule'] == 'parse.error')
    assert diagnostic['line'] == 3 and len(diagnostic['message']) < 500
    manifest = _cli('manifest', str(bad), '--format', 'json', env=environment)
    assert manifest.returncode == 2 and 'Traceback' not in manifest.stderr
    assert json.loads(manifest.stdout)['result']['state'] == 'infrastructure-error'
