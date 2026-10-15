"""Prospective, bounded replay of the maintainer SARIF report protocol."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sarif_workflow import ROOT, SKILL, input_identity, sha, workflow

from tracemantle.bundle import create_manifest
from tracemantle.evidence import Evidence, evidence_from_dict
from tracemantle.parser import parse
from tracemantle.storage import digest

CONSUMER = 'b5d86f339bd25cf85d86f6d6a545159e8a3cc9c3'
HISTORY = ('721845b35ef450ebaaf4c7bfb20990db92d0ed3c', '192cfb6d11f3fbf568da16b1ace484fdfead6287',
           'cd63b4991002258fda2a7f76edec16628056056f', 'ce6c4f0cfb78ee82aee6e84fa7aa0ccbe38d2df9', 'b1f68fb13b4fcf4edb43d4eea19e079d132bcd69')
FAULTS = ('invalid-metadata', 'missing-helper', 'changed-helper', 'changed-query', 'shared-fixture',
          'description', 'unrelated', 'checker', 'configuration', 'environment', 'model',
          'missing-evidence', 'expired-evidence', 'conflicting-evidence', 'unapproved-evidence', 'scanner-finding')


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n')


def checkout(revision: str, destination: Path) -> str:
    full = subprocess.check_output(['git', 'rev-parse', revision], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', full], cwd=ROOT)
    destination.mkdir()
    archive = destination.parent / 'source.tar'
    archive.write_bytes(raw)
    # Trusted, owner-controlled Git archive, never an evaluator-supplied archive.
    with tarfile.open(archive) as stream:
        stream.extractall(destination, filter='data')
    archive.unlink()
    return full


def policy(root: Path, record: Evidence, approved: list[str], *, variant: str = '') -> str:
    (root / 'records').mkdir(exist_ok=True)
    write(root / 'records/report.json', record.to_dict())
    checker = ROOT / 'scripts/sarif_workflow.py'
    shutil.copyfile(checker, root / 'checker.py')
    identity = record.configuration_sha256
    context = dict(record.environment)
    context['model'] = record.model
    if variant == 'environment':
        context['python'] = 'controlled-incompatible-version'
    if variant == 'model':
        context['model'] = 'controlled-different-model-identity'
    if variant == 'configuration':
        identity = digest({'changed': 'configuration'})
    if variant == 'checker':
        with (root / 'checker.py').open('a') as stream:
            stream.write('\n# Controlled checker revision.\n')
    text = f'''[tool.tracemantle.release]
schema_version=1
trusted_evidence={json.dumps(approved)}
[[tool.tracemantle.release.checks]]
id="report"
kind="static"
inputs={json.dumps([p for p, _ in record.inputs])}
coverage_complete=false
checker_path="checker.py"
checker_sha256="{sha(root / 'checker.py')}"
configuration_sha256="{identity}"
fixture_sha256="{record.fixture_sha256}"
profile_sha256="{record.profile_sha256}"
max_age_seconds=86400
required=true
routing_neighbors=[]
[tool.tracemantle.release.checks.context]
'''
    text += ''.join(f'{key}={json.dumps(value)}\n' for key, value in sorted(context.items()))
    (root / 'policy.toml').write_text(text)
    env = dict(os.environ, GIT_AUTHOR_NAME='TraceMantle study', GIT_COMMITTER_NAME='TraceMantle study',
               GIT_AUTHOR_EMAIL='study@example.invalid', GIT_COMMITTER_EMAIL='study@example.invalid')
    for command in (['git', 'init', '-q'], ['git', 'add', '.'], ['git', 'commit', '-qm', 'Approve measured report under frozen protocol']):
        subprocess.run(command, cwd=root, env=env, capture_output=True, check=True)
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def mutate(case: str, skill: Path, project: Path) -> None:
    path = skill / 'SKILL.md'
    if case == 'invalid-metadata':
        path.write_text(path.read_text().replace('name: sarif-parsing', 'name: 42'))
    elif case == 'missing-helper':
        (skill / 'resources/sarif_helpers.py').unlink()
    elif case == 'changed-helper':
        helper = skill / 'resources/sarif_helpers.py'
        helper.write_text(helper.read_text().replace('"total": len(findings)', '"total": len(findings) + 1'))
    elif case == 'changed-query':
        query = skill / 'resources/jq-queries.md'
        query.write_text(query.read_text().replace('def level($run):', 'def level($run) BROKEN:'))
    elif case == 'shared-fixture':
        fixture = skill / 'resources/fixtures/codeql-no-level.sarif'
        data = json.loads(fixture.read_bytes())
        for rule in data['runs'][0]['tool']['driver']['rules']:
            rule.setdefault('defaultConfiguration', {})['level'] = 'none'
        write(fixture, data)
    elif case == 'description':
        path.write_text(path.read_text().replace('Triggers on "parse sarif"', 'Triggers on "summarize sarif"'))
    elif case == 'unrelated':
        (skill / 'maintainer-note.txt').write_text('Reviewed licensing; no runtime change.\n')
    elif case == 'scanner-finding':
        (project / 'src/study_unused_import.py').write_text('import unused_dependency\n')


def seed(output: Path) -> None:
    from sarif_workflow import SETTINGS
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='sarif-seed-') as directory:
        project = Path(directory) / 'project'
        revision = checkout(CONSUMER, project)
        skill = project / 'integrations/sarif/vendor/sarif-parsing'
        result = workflow(project, skill, output / 'run', integrated=False)
        if result['scan_exit'] or any(c['errors'] for c in result['checks']):
            raise RuntimeError('Cannot approve a failed seed run')
        manifest = create_manifest(skill, document=parse(skill / 'SKILL.md', settings=SETTINGS))
        artifact = digest({p.name: sha(p) for p in sorted((output / 'run').iterdir()) if p.is_file()})
        record = Evidence('report', 'pass', manifest.sha256, input_identity(project), digest({'format': 'sarif-2.1.0', 'dialect': 'skill-base-dir'}),
                          sha(ROOT / 'scripts/sarif_workflow.py'), sha(output / 'run/scan.stdout'), artifact,
                          tuple((f.path, f.sha256) for f in manifest.files), datetime.now(timezone.utc).isoformat(),
                          'static-analysis', 'CPython', 'sarif-workflow-v1', 'none', 'none', False,
                          ('read-bundle', 'execute-helper', 'write-output'),
                          (('python', result['python']), ('os', result['platform'])), (),
                          'Measured SARIF analysis matched independent Ruff JSON; deterministic helper use, no agent.')
        write(output / 'record.json', record.to_dict())
        write(output / 'baseline.json', manifest.to_dict())
        write(output / 'source.json', {'revision': revision, 'scored': False, 'purpose': 'approval setup'})


def evaluate(output: Path, seed_root: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    record = evidence_from_dict(json.loads((seed_root / 'record.json').read_bytes()))
    cases = [('control', CONSUMER), *[(f'history-{i}', r) for i, r in enumerate(HISTORY)], *[(f, CONSUMER) for f in FAULTS]]
    for name, revision in cases:
        for repetition in range(3):
            if time.perf_counter() - started > 1200:
                raise TimeoutError('Scored deterministic evaluation exceeded 20 minutes')
            with tempfile.TemporaryDirectory(prefix='sarif-case-') as directory:
                work = Path(directory)
                project = work / 'project'
                full_revision = checkout(revision, project)
                skill = work / 'sarif-parsing'
                shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
                mutate(name, skill, project)
                trusted = work / 'trusted'
                trusted.mkdir()
                shutil.copyfile(seed_root / 'baseline.json', trusted / 'baseline.json')
                selected = record
                if name == 'expired-evidence':
                    selected = replace(record, observed_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat())
                approved = [] if name == 'unapproved-evidence' else [selected.sha256]
                trusted_revision = policy(trusted, selected, approved, variant=name)
                if name == 'missing-evidence':
                    (trusted / 'records/report.json').unlink()
                if name == 'conflicting-evidence':
                    # Controlled trust fault, never counted as an observed check failure.
                    conflict = replace(record, state='fail', reason='Injected conflicting approval, not an observed failure.')
                    write(trusted / 'records/conflict.json', conflict.to_dict())
                    trusted_revision = policy(trusted, record, [record.sha256, conflict.sha256])
                case_output = output / f'{name}-{repetition}'
                case_output.mkdir()
                shutil.copytree(trusted, case_output / 'trusted', ignore=shutil.ignore_patterns('.git'))
                write(case_output / 'source.json', {'revision': full_revision, 'case': name,
                                                   'kind': 'historical-replay' if name.startswith('history') else 'control' if name == 'control' else 'controlled-fault-or-change'})
                # C decision and execution precede B. A/B order alternates to expose order effects.
                order = ('C', 'A', 'B') if repetition % 2 == 0 else ('C', 'B', 'A')
                runs = {}
                for arm in order:
                    isolated = work / arm
                    shutil.copytree(project, isolated)
                    isolated_skill = work / f'{arm}-skill' / 'sarif-parsing'
                    shutil.copytree(skill, isolated_skill)
                    runs[arm] = workflow(isolated, isolated_skill, case_output / arm, integrated=arm == 'C',
                                         trusted_revision=trusted_revision if arm == 'C' else None,
                                         evidence_root=trusted if arm == 'C' else None)
                row = {'case': name, 'repetition': repetition, 'revision': full_revision, 'order': order, 'arms': runs}
                rows.append(row)
                write(output / 'results.json', {'rows': rows, 'elapsed_seconds': time.perf_counter() - started,
                                              'model_calls': 0, 'tokens': 0, 'model_cost_usd': 0})
                print(f'{name} repetition {repetition}: {runs["C"]["gate"]["state"]}', flush=True)
    write(output / 'hashes.json', {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'evaluate'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=Path)
    args = parser.parse_args()
    if args.action == 'seed':
        seed(args.output.resolve())
    elif args.seed:
        evaluate(args.output.resolve(), args.seed.resolve())
    else:
        parser.error('--seed is required for evaluation')


if __name__ == '__main__':
    main()
