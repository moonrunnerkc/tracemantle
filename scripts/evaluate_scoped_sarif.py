"""Bounded deterministic comparison; no model execution or behavioral evidence."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from evaluate_sarif_workflow import CONSUMER, HISTORY, checkout, mutate, write
from sarif_reuse import ELIGIBLE, identities
from sarif_workflow import ROOT, SKILL, execute, sha, workflow

from tracemantle.bundle import create_manifest
from tracemantle.evidence import Evidence, evidence_from_dict
from tracemantle.parser import DocumentSettings, parse
from tracemantle.storage import digest

CASES = [('control', CONSUMER), *[(f'history-{i}', r) for i, r in enumerate(HISTORY)],
         *[(name, CONSUMER) for name in ('invalid-metadata', 'missing-helper', 'changed-helper', 'changed-query',
                                       'shared-fixture', 'description', 'unrelated', 'scanner-finding',
                                       'documented-command', 'unresolved-module')]]


def git_commit(root: Path) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME='moonrunnerkc', GIT_COMMITTER_NAME='moonrunnerkc',
               GIT_AUTHOR_EMAIL='study@example.invalid', GIT_COMMITTER_EMAIL='study@example.invalid')
    for args in (['init', '-q'], ['add', '.'], ['commit', '-qm', 'Approve measured maintenance evidence']):
        subprocess.run(['git', *args], cwd=root, env=env, check=True, capture_output=True)
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def seed(output: Path, current_project: Path | None = None) -> None:
    output.mkdir(parents=True)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='scoped-seed-') as tmp:
        project = Path(tmp) / 'project'
        revision = checkout(CONSUMER, project) if current_project is None else subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=current_project, text=True).strip()
        if current_project is not None:
            project = current_project
        skill = project / 'integrations/sarif/vendor/sarif-parsing'
        result = workflow(project, skill, output / 'run', integrated=False)
        if result['scan_exit'] or any(c['errors'] for c in result['checks']):
            raise RuntimeError('Seed checks must actually pass before approval')
        values, unresolved = identities(skill)
        if unresolved:
            raise RuntimeError(f'Unresolved seed inputs: {unresolved}')
        manifest = create_manifest(skill, document=parse(skill / 'SKILL.md', settings=DocumentSettings(reference_format='skill-base-dir')))
        write(output / 'baseline.json', manifest.to_dict())
        write(output / 'cache.json', {c: values[c]['key'] for c in ELIGIBLE})
        (output / 'records').mkdir()
        shutil.copyfile(ROOT / 'scripts/sarif_workflow.py', output / 'checker.py')
        checks, approved = [], []
        for check in ELIGIBLE:
            value = values[check]
            (output / f'{check}.json').write_text(json.dumps(value['scope'], sort_keys=True, indent=2) + '\n')
            record = Evidence(check, 'pass', manifest.sha256, value['configuration_sha256'], value['profile_sha256'],
                              sha(output / 'checker.py'), digest({'fixtures': 'included in input set'}),
                              digest({p.name: sha(p) for p in sorted((output / 'run').iterdir()) if p.is_file()}),
                              tuple((p, value['inputs'][p][0]) for p in value['scope']['inputs']),
                              datetime.now(timezone.utc).isoformat(), 'observed-execution', 'CPython', 'sarif-maintenance-v2',
                              'none', 'none', False, ('read-bundle', 'execute-helper', 'write-output'),
                              (('os', result['platform']), ('python', result['python'])), (),
                              'Actual deterministic maintenance execution passed; no agent or model used.')
            record = evidence_from_dict(record.to_dict())
            write(output / f'records/{check}.json', record.to_dict())
            approved.append(record.sha256)
            checks.append(f'''[[tool.tracemantle.release.checks]]
id={json.dumps(check)}
kind="deterministic"
inputs={json.dumps(value['scope']['inputs'])}
coverage_complete=true
checker_path="checker.py"
checker_sha256="{record.checker_sha256}"
configuration_sha256="{record.configuration_sha256}"
fixture_sha256="{record.fixture_sha256}"
profile_sha256="{record.profile_sha256}"
input_scope_path="{check}.json"
max_age_seconds=86400
required=true
routing_neighbors=[]
context={{runner="CPython", adapter="sarif-maintenance-v2", python={json.dumps(result['python'])}, os={json.dumps(result['platform'])}}}
''')
        (output / 'policy.toml').write_text('[tool.tracemantle.release]\nschema_version=3\ntrusted_evidence=' + json.dumps(approved) + '\n' + '\n'.join(checks))
        trusted = git_commit(output)
        write(output / 'seed.json', {'consumer': revision, 'trusted_revision': trusted, 'seconds': time.perf_counter() - started,
                                     'implementation': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                                     'identities': values})
        subprocess.run(['git', 'bundle', 'create', str(output / 'trusted.bundle'), '--all'], cwd=output, check=True, capture_output=True)


def change(case: str, skill: Path, project: Path) -> None:
    mutate(case, skill, project)
    if case == 'documented-command':
        path = skill / 'SKILL.md'
        path.write_text(path.read_text().replace('HIGH_COUNT=$(jq', 'HIGH_COUNT=$(broken'))
    elif case == 'unresolved-module':
        (skill / 'resources/new_runtime.py').write_text('"""Unreviewed new module; no closed dependency assertion."""\n')


def invocation(arm: str, project: Path, skill: Path, output: Path, trust: Path, revision: str) -> dict[str, Any]:
    argv = [sys.executable, str(ROOT / 'scripts/sarif_workflow.py'), '--project', str(project), '--skill', str(skill), '--output', str(output)]
    if arm == 'B':
        argv += ['--reuse-cache', str(trust)]
    elif arm == 'C':
        argv += ['--integrated', '--evidence-root', str(trust), '--trusted-revision', revision]
    command = execute(argv, ROOT, output.parent / f'{arm}-invocation')
    if not (output / 'run.json').exists():
        raise RuntimeError(f'Infrastructure failure, retained at {output.parent}')
    result: dict[str, Any] = json.loads((output / 'run.json').read_bytes())
    result['invocation'] = command
    return result


def verify(runs: dict[str, Any], case: str) -> dict[str, Any]:
    reference = {c['id']: c for c in runs['D']['checks']}
    expected_failures = {'invalid-metadata': {'bundle-contract'}, 'missing-helper': {'bundle-contract', 'report', 'upstream-tests'},
                         'changed-helper': {'report'}, 'changed-query': {'report', 'upstream-tests'},
                         'shared-fixture': {'upstream-tests'}, 'documented-command': {'upstream-tests'}}
    assert {c for c, value in reference.items() if value['errors']} == expected_failures.get(case, set()), (case, reference)
    assert runs['D']['scan_exit'] == (1 if case == 'scanner-finding' else 0)
    failures = []
    justified = {'B': 0, 'C': 0}
    for arm in ('A', 'B', 'C'):
        if runs[arm]['scan_exit'] != runs['D']['scan_exit']:
            failures.append(f'{arm} scanner disagrees')
        for check in runs[arm]['checks']:
            expected = reference[check['id']]
            if bool(check['errors']) != bool(expected['errors']):
                failures.append(f'{arm} {check["id"]} disagrees')
            if check['reused']:
                if check['id'] not in ELIGIBLE or expected['errors']:
                    failures.append(f'{arm} invalid skip of {check["id"]}')
                else:
                    justified[arm] += 1
        # Report executes against the current scan in every arm, even on cache hits.
        report_check = next(c for c in runs[arm]['checks'] if c['id'] == 'report')
        assert not report_check['reused']
        if case == 'scanner-finding':
            assert runs[arm]['scan_exit'] == 1 and not report_check['errors']
    return {'failures': failures, 'reference_failed': bool(runs['D']['scan_exit'] or any(c['errors'] for c in reference.values())),
            'justified_skips': justified}


def evaluate(output: Path, trust: Path, *, preflight: bool = False) -> None:
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    seed_data = json.loads((trust / 'seed.json').read_bytes())
    revision = seed_data['trusted_revision']
    rows = []
    for index, (case, source) in enumerate(CASES):
        for repetition in range(1 if preflight else 3):
            if time.perf_counter() - started > 1200:
                raise TimeoutError('20-minute cap reached; retain partial results')
            directory = output / f'{case}-{repetition}'
            directory.mkdir()
            with tempfile.TemporaryDirectory(prefix='scoped-case-') as tmp:
                work = Path(tmp)
                project = work / 'source'
                checkout(source, project)
                skill = work / 'sarif-parsing'
                shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
                change(case, skill, project)
                offset = (index + repetition) % 3
                order = ['A', 'B', 'C'][offset:] + ['A', 'B', 'C'][:offset] + ['D']
                runs = {}
                for arm in order:
                    isolated = work / arm
                    shutil.copytree(project, isolated)
                    isolated_skill = work / f'{arm}-skill' / 'sarif-parsing'
                    shutil.copytree(skill, isolated_skill)
                    runs[arm] = invocation(arm, isolated, isolated_skill, directory / arm, trust, revision)
                verification = verify(runs, case)
                expected_skips = 2 if case == 'control' or case.startswith('history-') or case in {'unrelated', 'scanner-finding'} else 1 if case == 'unresolved-module' else 0
                for arm in ('B', 'C'):
                    assert len(runs[arm]['gate']['reuse']) == expected_skips, (case, arm, runs[arm]['gate'])
                    for check in runs[arm]['checks']:
                        if check['reused']:
                            assert runs[arm]['gate']['identities'][check['id']] == seed_data['identities'][check['id']]
                    report_path = directory / arm / 'python-report.stdout'
                    if case == 'scanner-finding':
                        current_report = json.loads(report_path.read_bytes())
                        assert current_report['summary']['total'] == 1
                        assert current_report['findings'][0][0] == 'F401'
                        assert current_report['findings'][0][2].endswith('/src/study_unused_import.py')
                # Both mechanisms bind exactly the same scope, current inputs and execution context.
                for check in runs['C']['checks']:
                    if check['reused']:
                        identity = runs['C']['gate']['identities'][check['id']]
                        assert identity == seed_data['identities'][check['id']]
                        assert check['id'] in runs['B']['gate']['reuse']
                rows.append({'case': case, 'revision': source, 'repetition': repetition, 'order': order, 'arms': runs, 'verification': verification})
                write(output / 'results.json', {'rows': rows, 'seconds': time.perf_counter() - started, 'preflight': preflight,
                                                'implementation': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                                                'model_calls': 0, 'tokens': 0, 'model_cost_usd': 0})
                if verification['failures']:
                    raise AssertionError(verification)
                print(case, repetition, verification, flush=True)
    write(output / 'hashes.json', {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def approval_preflight(output: Path, seed_root: Path) -> None:
    """Security controls are not scored as optimization wins over a cache."""
    output.mkdir()
    results = []
    for fault in ('missing', 'expired', 'conflict', 'altered', 'unapproved', 'checker', 'configuration', 'environment', 'declaration', 'candidate-policy'):
        with tempfile.TemporaryDirectory() as tmp:
            trust = Path(tmp) / 'trust'
            shutil.copytree(seed_root, trust)
            record_path = trust / 'records/upstream-tests.json'
            record = evidence_from_dict(json.loads(record_path.read_bytes()))
            policy_path = trust / 'policy.toml'
            policy = policy_path.read_text()
            if fault == 'missing':
                record_path.unlink()
            elif fault == 'altered':
                write(record_path, replace(record, reason='Changed after approval').to_dict())
            elif fault in {'expired', 'conflict'}:
                changed = replace(record, observed_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()) if fault == 'expired' else replace(record, state='fail', reason='Injected approval conflict, not an observed failure')
                write(record_path if fault == 'expired' else trust / 'records/conflict.json', changed.to_dict())
                policy = policy.replace(f'"{record.sha256}"', f'"{changed.sha256}"' + (f', "{record.sha256}"' if fault == 'conflict' else ''))
            elif fault == 'unapproved':
                policy = policy.replace(record.sha256, 'f' * 64)
            elif fault in {'checker', 'configuration', 'environment', 'declaration'}:
                if fault == 'checker':
                    (trust / 'checker.py').write_text('# Changed checker\n')
                    policy = policy.replace(record.checker_sha256, sha(trust / 'checker.py'))
                elif fault == 'configuration':
                    policy = policy.replace(record.configuration_sha256, 'e' * 64)
                elif fault == 'environment':
                    policy = policy.replace('python="', 'python="changed-')
                else:
                    path = trust / 'upstream-tests.json'
                    scope = json.loads(path.read_bytes())
                    scope['assumptions'].append('Additional reviewed constraint')
                    write(path, scope)
                    policy = policy.replace(record.profile_sha256, sha(path))
            policy_path.write_text(policy)
            if fault in {'missing', 'altered', 'candidate-policy'}:
                revision = json.loads((trust / 'seed.json').read_bytes())['trusted_revision']
            else:
                revision = git_commit(trust)
            if fault == 'candidate-policy':
                policy_path.write_text('[tool.tracemantle.release]\nchecks=[]')
                (trust / 'upstream-tests.json').write_text('{}')
            with tempfile.TemporaryDirectory() as project_tmp:
                project = Path(project_tmp) / 'project'
                checkout(CONSUMER, project)
                skill = project / 'integrations/sarif/vendor/sarif-parsing'
                run = invocation('C', project, skill, output / fault, trust, revision)
                reference = invocation('D', project, skill, output / (fault + '-reference'), trust, revision)
                reused = 'upstream-tests' in run['gate']['reuse']
                assert reused == (fault == 'candidate-policy'), fault
                assert not any(c['errors'] for c in reference['checks'])
                results.append({'fault': fault, 'reuse': run['gate']['reuse'], 'decision': run['gate'], 'reference_pass': True})
    write(output / 'results.json', results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'preflight', 'evaluate', 'approvals'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--project', type=Path, help='Actual deployment source for seed; omitted for pinned study replay')
    args = parser.parse_args()
    if args.action == 'seed':
        seed(args.output.resolve(), args.project.resolve() if args.project else None)
    elif args.seed is None:
        parser.error('--seed is required')
    elif args.action == 'approvals':
        approval_preflight(args.output.resolve(), args.seed.resolve())
    else:
        evaluate(args.output.resolve(), args.seed.resolve(), preflight=args.action == 'preflight')


if __name__ == '__main__':
    main()
