"""--require-observed-execution and the external runner example.

The "agent" below is a one-line Python command. Nothing here is a live agent or
model run; the tests cover the record format and the gate, not skill behavior.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from tests.test_build_plan_product import NOW, _bundle, _policy, _record
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.evidence import evidence_from_dict

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / 'docs/examples/observed_execution_runner.py'
ADAPTER = REPO_ROOT / 'docs/examples/observed_execution_adapter.py'
SCHEMA = REPO_ROOT / 'docs/schemas/observed-execution-v1.json'
CHECKER = 'import json, sys\ntranscript = json.load(open(sys.argv[1]))\nok = "skill loaded" in transcript["stdout"]\nprint("found marker" if ok else "marker missing")\nsys.exit(0 if ok else 1)\n'


def _run_reference_runner(tmp_path: Path, bundle: Path, agent_output: str) -> dict[str, object]:
    checks = tmp_path / 'checks'
    checks.mkdir(exist_ok=True)
    (checks / 'checker.py').write_text(CHECKER)
    for name in ('config.json', 'prompt.txt', 'profile.json'):
        (checks / name).write_text(f'synthetic {name}\n')
    out = tmp_path / 'out'
    result = subprocess.run(
        [sys.executable, str(RUNNER), '--bundle', str(bundle), '--check-id', 'invoke', '--checker', str(checks / 'checker.py'),
         '--configuration', str(checks / 'config.json'), '--fixture', str(checks / 'prompt.txt'), '--profile', str(checks / 'profile.json'),
         '--model', 'synthetic-model', '--model-revision', 'sha256:' + '0' * 64, '--model-immutable', '--tokenizer', 'synthetic-tokenizer',
         '--sandbox', 'tmpdir', '--output-dir', str(out), '--', sys.executable, '-c', f'import sys; sys.stdin.read(); print({agent_output!r})'],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    record: dict[str, object] = json.loads(Path(result.stdout.strip()).read_text())
    return record


def _import(tmp_path: Path, bundle: Path, record: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', 'import-evidence', str(record), '--adapter', str(ADAPTER),
                           '--bundle', str(bundle), '--store', str(tmp_path / 'store'), '--format', 'json'], capture_output=True, text=True)


def _trusted_policy(root: Path, kind: str, stored: dict[str, object], digest: str) -> str:
    root.mkdir()
    shutil.copy(root.parent / 'checks/checker.py', root / 'checker.py')
    (root / 'pyproject.toml').write_text(f'''[tool.tracemantle.release]
schema_version=1
trusted_evidence=["{digest}"]
[[tool.tracemantle.release.checks]]
id="invoke"
kind="{kind}"
inputs=["SKILL.md"]
coverage_complete=true
checker_path="checker.py"
checker_sha256="{stored['checker_sha256']}"
configuration_sha256="{stored['configuration_sha256']}"
fixture_sha256="{stored['fixture_sha256']}"
profile_sha256="{stored['profile_sha256']}"
max_age_seconds=3600
required=true
routing_neighbors=[]
context={{runner="{stored['runner']}", adapter="{stored['adapter']}", sandbox="tmpdir"}}
''')
    for args in [['init', '-q'], ['add', '.'], ['-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid', 'commit', '-qm', 'Synthetic trusted policy fixture']]:
        subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


def _compare(bundle: Path, trust: Path, revision: str, record: str, *extra: str) -> tuple[int, dict[str, object]]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'compare', str(bundle), str(bundle), '--trusted-root', str(trust),
                             '--base-revision', revision, '--evidence', record, '--format', 'json', *extra], capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)['result']


def test_runner_record_passes_the_gate_only_after_import_and_trusted_approval(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    record = _run_reference_runner(tmp_path, bundle, 'skill loaded')
    assert record['outcome'] == 'pass' and record['reason'] == 'found marker'
    assert record['bundle_sha256'] == create_manifest(bundle).sha256
    transcript = tmp_path / 'out/invoke.transcript.json'
    assert record['artifact_sha256'] == hashlib.sha256(transcript.read_bytes()).hexdigest()
    assert json.loads(transcript.read_text())['exit_code'] == 0

    imported = _import(tmp_path, bundle, tmp_path / 'out/invoke.observed.json')
    assert imported.returncode == 4, imported.stdout + imported.stderr
    stored_path = json.loads(imported.stdout)['result']['records'][0]
    stored = json.loads(Path(stored_path).read_bytes())
    assert stored['observation_method'] == 'observed-execution'
    assert stored['adapter'] == 'external/sha256:' + hashlib.sha256(ADAPTER.read_bytes()).hexdigest()
    assert stored['runner'] == 'tracemantle-reference-runner/sha256:' + hashlib.sha256(RUNNER.read_bytes()).hexdigest()

    unapproved = _trusted_policy(tmp_path / 'unapproved', 'behavioral', stored, 'f' * 64)
    code, result = _compare(bundle, tmp_path / 'unapproved', unapproved, stored_path, '--require-observed-execution')
    assert code == 4 and result['state'] == 'unknown', 'a fresh run is not trusted until its digest is approved'

    revision = _trusted_policy(tmp_path / 'trust', 'behavioral', stored, Path(stored_path).stem)
    code, result = _compare(bundle, tmp_path / 'trust', revision, stored_path, '--require-observed-execution')
    assert code == 0 and result['state'] == 'pass', result


def test_runner_records_a_failed_check_and_an_unstartable_command(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    failed = _run_reference_runner(tmp_path, bundle, 'no such skill')
    assert failed['outcome'] == 'fail' and failed['reason'] == 'marker missing'
    result = subprocess.run(
        [sys.executable, str(RUNNER), '--bundle', str(bundle), '--check-id', 'missing', '--checker', str(tmp_path / 'checks/checker.py'),
         '--configuration', str(tmp_path / 'checks/config.json'), '--fixture', str(tmp_path / 'checks/prompt.txt'),
         '--profile', str(tmp_path / 'checks/profile.json'), '--model', 'm', '--model-revision', 'r', '--tokenizer', 't',
         '--output-dir', str(tmp_path / 'out'), '--', str(tmp_path / 'no-such-agent-binary')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    record = json.loads((tmp_path / 'out/missing.observed.json').read_text())
    assert record['outcome'] == 'infrastructure-error' and 'could not start' in record['reason']


def test_runner_refuses_to_write_into_the_bundle(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    result = subprocess.run([sys.executable, str(RUNNER), '--bundle', str(bundle), '--check-id', 'c', '--checker', 'c', '--configuration', 'c',
                             '--fixture', 'c', '--profile', 'c', '--model', 'm', '--model-revision', 'r', '--tokenizer', 't',
                             '--output-dir', str(bundle / 'out'), '--', 'agent'], capture_output=True, text=True)
    assert result.returncode == 2 and 'outside the bundle' in result.stderr
    assert not (bundle / 'out').exists()


def test_static_evidence_passes_by_default_and_is_unknown_when_observed_execution_is_required(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    _run_reference_runner(tmp_path, bundle, 'skill loaded')
    relabelled = tmp_path / 'static.json'
    stored_path = json.loads(_import(tmp_path, bundle, tmp_path / 'out/invoke.observed.json').stdout)['result']['records'][0]
    static = json.loads(Path(stored_path).read_bytes()) | {'observation_method': 'static-analysis'}
    relabelled.write_text(json.dumps(static))
    revision = _trusted_policy(tmp_path / 'trust', 'static', static, evidence_from_dict(static).sha256)
    code, result = _compare(bundle, tmp_path / 'trust', revision, str(relabelled))
    assert code == 0 and result['state'] == 'pass', result
    code, result = _compare(bundle, tmp_path / 'trust', revision, str(relabelled), '--require-observed-execution')
    assert code == 4 and result['state'] == 'unknown'
    assert 'Observed execution is required' in result['checks'][0]['reasons'][0]  # type: ignore[index]
    assert result['required_reruns'] == ['invoke']


def test_requiring_observed_execution_does_not_soften_failures_or_touch_optional_checks(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    manifest = create_manifest(bundle)
    static = replace(_record(bundle), observation_method='static-analysis')
    policy = _policy(static, kind='static')
    assert compare(manifest, manifest, (static,), policy, now=NOW, require_observed_execution=True).state == 'unknown'
    failing = replace(static, state='fail')
    failed_policy = replace(policy, trusted_evidence=frozenset({failing.sha256}))
    assert compare(manifest, manifest, (failing,), failed_policy, now=NOW, require_observed_execution=True).state == 'fail'
    observed = _record(bundle)
    behavioral = _policy(observed)
    assert compare(manifest, manifest, (observed,), behavioral, now=NOW, require_observed_execution=True).state == 'pass'
    optional = replace(policy, checks=(replace(policy.checks[0], required=False), replace(behavioral.checks[0], id='invoke')),
                       trusted_evidence=frozenset({static.sha256, replace(observed, check_id='invoke').sha256}))
    result = compare(manifest, manifest, (static, replace(observed, check_id='invoke')), optional, now=NOW, require_observed_execution=True)
    assert result.state == 'pass' and {c.check_id: c.state for c in result.checks} == {'validate': 'pass', 'invoke': 'pass'}


def test_adapter_rejects_records_that_are_not_observed_executions(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    record = _run_reference_runner(tmp_path, bundle, 'skill loaded')
    for field, value, message in [('observation_method', 'model-judgment', 'does not relabel'), ('kind', 'check-evidence', 'Unsupported record'),
                                  ('outcome', 'success', 'Unknown evidence state'), ('extra', 1, 'exactly the documented fields')]:
        altered = tmp_path / f'{field}.json'
        altered.write_text(json.dumps(record | {field: value}))
        result = _import(tmp_path, bundle, altered)
        assert result.returncode == 2 and message in json.loads(result.stdout)['result']['reason'], field
    assert not (tmp_path / 'store').exists()


def test_schema_runner_and_adapter_agree_on_the_record_fields(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text())
    record = _run_reference_runner(tmp_path, _bundle(tmp_path / 'bundle'), 'skill loaded')
    assert {'check_id', 'outcome', 'observation_method', 'inputs_sha256', 'checker_sha256', 'context', 'artifact_sha256'} <= set(schema['required'])
    assert set(record) == set(schema['required']) == set(schema['properties'])
    assert schema['properties']['observation_method'] == {'const': 'observed-execution'}
    context = schema['properties']['context']
    assert set(record['context']) == set(context['required']) == set(context['properties'])  # type: ignore[call-overload]
    assert set(record['context']['environment']) <= set(context['properties']['environment']['properties'])  # type: ignore[index]
    namespace: dict[str, object] = {}
    exec(compile(ADAPTER.read_text(), str(ADAPTER), 'exec'), namespace)
    assert namespace['FIELDS'] == set(schema['required']) and namespace['CONTEXT_FIELDS'] == set(context['required'])
