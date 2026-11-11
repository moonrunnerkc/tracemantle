"""Dependency and numeric boundary regressions with synthetic approved evidence."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.test_build_plan_acceptance import _cli
from tests.test_build_plan_product import IDENTITY, NOW, UPSTREAM, _bundle, _record, _trusted_repository
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.evidence import Evidence
from tracemantle.markdown import tokenize
from tracemantle.policy import RequiredCheck, TrustedPolicy, load_trusted_policy
from tracemantle.storage import EvidenceError, canonical, decode_json, digest


@pytest.mark.parametrize('slashes', range(6))
def test_backtick_opening_escape_parity(slashes: int) -> None:
    result = tokenize('\\' * slashes + '` [helper](helper.py) `', 7)
    assert [(r.target, r.line) for r in result.resources] == ([('helper.py', 7)] if slashes % 2 else [])
    assert not result.uncertain


@pytest.mark.parametrize('body,targets', [
    (r'\`` [example](missing.md) ` [helper](helper.py)', ['helper.py']),
    (r'\`` [helper](helper.py) ``', ['helper.py']),
    (r'`code\` [helper](helper.py) `', ['helper.py']),
    (r'``code\`` [helper](helper.py) ``', ['helper.py']),
    (r'`` code\` [example](missing.md) `` [helper](helper.py)', ['helper.py']),
    (r'\` [helper](helper.py) ``', ['helper.py']),
    (r'` [helper](helper.py) ``', ['helper.py']),
    ('- `unclosed\n- [helper](helper.py) `', ['helper.py']),
    ('\\`\n[helper](helper.py)\n`', ['helper.py']),
])
def test_backtick_runs_and_literal_backslashes(body: str, targets: list[str]) -> None:
    assert [r.target for r in tokenize(body).resources] == targets


@pytest.mark.parametrize('body', [
    '- Steps:\n    - [helper](helper.py)',
    '- Steps:\n\t- [helper](helper.py)',
    '1. Steps:\n    1. [helper](helper.py)',
    '- Steps:\n    [helper](helper.py)',
    '- Steps:\n\n    [helper](helper.py)',
    '-\tSteps:\n\n    [helper](helper.py)',
    '1.\tSteps:\n\n    [helper](helper.py)',
    '- Steps:\n    - Nested:\n        [helper](helper.py)',
    'Paragraph\n    [helper](helper.py)',
    '- Steps:\n    [ref]: helper.py\n\n    [ref]',
])
def test_list_and_paragraph_continuations_keep_dependencies(body: str) -> None:
    result = tokenize(body, 5)
    assert [(r.target, r.line) for r in result.resources] == [('helper.py', 5 + body[:body.index('helper.py')].count('\n'))]
    assert not result.uncertain


@pytest.mark.parametrize('body', [
    '- Steps:\n\n      [example](missing.md)',
    '- Steps:\n    ```md\n    [example](missing.md)\n    ```',
    '- Steps:\n    - Nested:\n\n          [example](missing.md)',
    '    - [example](missing.md)',
    '- Steps:\n\n\t  [example](missing.md)',
])
def test_list_code_examples_stay_excluded(body: str) -> None:
    result = tokenize(body)
    assert result.resources == ()
    assert not result.uncertain


@pytest.mark.parametrize('body,complete,dependency', [
    ('[helper](helper.py)', True, True),
    (r'\` [helper](helper.py) `', True, True),
    ('- Steps:\n    - [helper](helper.py)', True, True),
    ('- Steps:\n\n    [helper](helper.py)', True, True),
    ('Paragraph\n    [helper](helper.py)', True, True),
    ('> - Steps:\n>     [helper](helper.py)', False, True),
    ('- Steps:\nlazy continuation\n\n    [helper](helper.py)', False, False),
    ('- - Steps:\n\n    [helper](helper.py)', False, True),
    ('-\n\n     [helper](helper.py)', True, True),
    ('`[example](helper.py)`', True, False),
    ('- Steps:\n\n      [example](helper.py)', True, False),
])
def test_dependency_closure_controls_real_trusted_comparison(tmp_path: Path, body: str, complete: bool, dependency: bool) -> None:
    base = _bundle(tmp_path / 'base')
    source = base / 'SKILL.md'
    source.write_text(source.read_text().replace('Run [helper](helper.py).', body))
    # Both policy and evidence bind ONLY SKILL.md. Binding helper.py would mask
    # the dependency-discovery defect by independently governing its digest.
    record = _record(base)
    record = replace(record, inputs=tuple(item for item in record.inputs if item[0] == 'SKILL.md'),
                     observed_at=datetime.now(timezone.utc).isoformat())
    trusted = tmp_path / 'trusted'
    _trusted_repository(trusted, record)
    policy_file = trusted / 'pyproject.toml'
    policy_file.write_text(policy_file.read_text().replace('inputs=["SKILL.md", "helper.py"]', 'inputs=["SKILL.md"]'))
    subprocess.run(['git', '-C', str(trusted), 'add', '.'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(trusted), '-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid',
                    'commit', '-qm', 'Declare only the skill input'], check=True, capture_output=True)
    revision = subprocess.check_output(['git', '-C', str(trusted), 'rev-parse', 'HEAD'], text=True).strip()
    assert load_trusted_policy(trusted, revision).checks[0].inputs == ('SKILL.md',)
    assert set(json.loads((trusted / 'approved.json').read_bytes())['inputs']) == {'SKILL.md'}
    manifest = _cli('manifest', str(base), '--format', 'json')
    identity = json.loads(manifest.stdout)['result']
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    args = ('compare', str(base), str(candidate), '--trusted-root', str(trusted), '--base-revision', revision,
            '--evidence', str(trusted / 'approved.json'), '--format', 'json')
    unchanged = _cli(*args)
    assert unchanged.returncode == (0 if complete else 4)
    (candidate / 'notes.txt').write_text('Unrelated change')
    unrelated = _cli(*args)
    assert unrelated.returncode == (0 if complete else 4)
    (candidate / 'notes.txt').unlink()
    (candidate / 'helper.py').write_text('print("changed helper")\n')
    result = _cli(*args)
    report = json.loads(result.stdout)
    invalidated = dependency or not complete
    assert result.returncode == report['exit_code'] == (4 if invalidated else 0)
    assert report['result']['state'] == ('unknown' if invalidated else 'pass')
    assert report['result']['changed_inputs'] == ['helper.py']
    assert report['result']['required_reruns'] == (['validate'] if invalidated else [])
    if not complete:
        assert 'coverage is incomplete' in result.stdout
    assert 'Traceback' not in result.stderr
    assert _cli(*args).stdout == result.stdout
    assert identity['complete'] is complete
    assert (['SKILL.md', 'helper.py'] in identity['dependencies']) is dependency


@pytest.mark.parametrize('literal', ['1e999', '-1e999', 'NaN', 'Infinity', '-Infinity'])
@pytest.mark.parametrize('container', ['{}', '{{"value":{}}}', '[{}]', '{{"nested":[{{"value":{}}}]}}'])
def test_shared_decoder_rejects_all_nonfinite_numbers(literal: str, container: str) -> None:
    raw = container.format(literal)
    for source in (raw, raw.encode()):
        with pytest.raises(EvidenceError, match='Non-finite') as raised:
            decode_json(source)
        assert len(str(raised.value)) < 200


@pytest.mark.parametrize('literal', ['1e308', '-1e308', '1.7976931348623157e308', '1e-308', '5e-324', '1e-999', '-1e-999', '0e999'])
def test_finite_exponents_preserve_canonical_bytes_and_digests(literal: str) -> None:
    raw = '{"nested":[' + literal + ']}'
    expected = json.loads(raw)
    assert math.isfinite(expected['nested'][0])
    decoded = decode_json(raw)
    expected_bytes = json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    assert canonical(decoded) == expected_bytes
    assert digest(decoded) == hashlib.sha256(expected_bytes).hexdigest()


@pytest.mark.parametrize('literal', ['1e999', '-1e999'])
@pytest.mark.parametrize('location', ['config', 'bound-row', 'unbound-row'])
def test_authentic_promptfoo_overflow_is_atomic_cli_error(tmp_path: Path, literal: str, location: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    data = json.loads(UPSTREAM.read_bytes())
    rows = data['results']['results']
    bindings = {'schema_version': 1, 'rows': {row['id']: _record(bundle).to_dict() for row in rows}}
    destination = data['config'] if location == 'config' else rows[-1]['testCase']
    destination['overflow_probe'] = 'RAW_OVERFLOW'
    if location == 'unbound-row':
        del bindings['rows'][rows[-1]['id']]
    source, bound, store = tmp_path / 'export.json', tmp_path / 'bindings.json', tmp_path / 'store'
    source.write_bytes(canonical(data).replace(b'"RAW_OVERFLOW"', literal.encode()))
    bound.write_bytes(canonical(bindings))
    for fmt in ('json', 'text', 'github'):
        result = _cli('import-evidence', str(source), '--bundle', str(bundle), '--bindings', str(bound), '--store', str(store), '--format', fmt)
        assert result.returncode == 2, result.stdout + result.stderr
        assert 'Traceback' not in result.stderr + result.stdout
        assert 'Non-finite' in result.stdout
        assert len(result.stdout + result.stderr) < 2000
        if fmt == 'json':
            report = json.loads(result.stdout)
            assert report['exit_code'] == 2 and report['result']['state'] == 'infrastructure-error'
        assert not store.exists()


@pytest.mark.parametrize('link', ['[helpers](scripts/)', '[helpers](scripts)'])
def test_directory_link_cannot_authorize_reuse_after_helper_change(tmp_path: Path, link: str) -> None:
    base = tmp_path / 'base'
    (base / 'scripts').mkdir(parents=True)
    (base / 'SKILL.md').write_text(f'---\nname: base\ndescription: Use when checking directory links.\n---\n\nRun the {link} first.\n')
    (base / 'scripts' / 'helper.py').write_text('print("safe")\n')
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    (candidate / 'scripts' / 'helper.py').write_text('print("changed helper")\n')
    baseline = create_manifest(base)
    assert baseline.complete is False
    record = Evidence('validate', 'pass', baseline.sha256, IDENTITY, IDENTITY, IDENTITY, IDENTITY, IDENTITY,
                      tuple((f.path, f.sha256) for f in baseline.files if f.path == 'SKILL.md'), NOW.isoformat(),
                      'static-analysis', 'synthetic-test', 'test/v1', 'none', 'none', True, (), (), (), 'Synthetic control.')
    check = RequiredCheck('validate', 'static', ('SKILL.md',), True, IDENTITY, IDENTITY, IDENTITY, IDENTITY, 3600, True, (), ())
    result = compare(baseline, create_manifest(candidate), (record,), TrustedPolicy('1' * 40, (check,), frozenset({record.sha256}), IDENTITY), now=NOW)
    assert result.changed_inputs == ('scripts/helper.py',)
    assert result.state == 'unknown'


@pytest.mark.parametrize('artifact', ['scripts/__pycache__/helper.cpython-312.pyc', 'scripts/.git'])
def test_unhashed_runtime_content_keeps_identity_incomplete(tmp_path: Path, artifact: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    (bundle / 'scripts').mkdir()
    clean = create_manifest(bundle)
    target = bundle / artifact
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'cached bytecode or nested repository content')
    polluted = create_manifest(bundle)
    # The hash still excludes these names; completeness is what changes.
    assert polluted.sha256 == clean.sha256
    assert clean.complete is True
    assert polluted.complete is False
    assert any('Unhashed runtime content' in issue for issue in polluted.issues)


def test_bundle_root_repository_metadata_does_not_affect_completeness(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    (bundle / '.git').mkdir()
    (bundle / '.git' / 'HEAD').write_text('ref: refs/heads/main\n')
    assert create_manifest(bundle).complete is True
