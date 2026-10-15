"""Run the maintainer's Ruff-to-SARIF report, with optional conservative evidence reuse."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'integrations/sarif/vendor/sarif-parsing'
CHECKS = ('bundle-contract', 'report', 'upstream-tests')
REQUIRED_FILES = ('SKILL.md', 'resources/sarif_helpers.py', 'resources/jq-queries.md',
                  'resources/test_sarif_helpers.py', 'resources/fixtures/codeql-no-level.sarif',
                  'resources/fixtures/levels-on-results.sarif')
REPORT_CODE = '''import json, sys
sys.path.insert(0, sys.argv[1])
from sarif_helpers import extract_findings, load_sarif, summary
findings = extract_findings(load_sarif(sys.argv[2]))
print(json.dumps({"summary": summary(findings), "findings": [
    [f.rule_id, f.level, f.file_path, f.start_line, f.message] for f in findings]}))
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_identity(project: Path) -> str:
    from tracemantle.storage import digest

    files = {str(p.relative_to(project)): sha(p) for directory in ('src', 'tests', 'scripts')
             for p in sorted((project / directory).rglob('*')) if p.is_file()
             and not {'__pycache__', '.pytest_cache', '.ruff_cache'} & set(p.parts)}
    for name in ('pyproject.toml', 'constraints-dev.txt'):
        files[name] = sha(project / name)
    jq = shutil.which('jq')
    if jq is None:
        raise RuntimeError('jq is required')
    from importlib.metadata import version
    return digest({'files': files, 'checker': sha(Path(__file__)), 'dialect': 'skill-base-dir',
                   'python': sys.version, 'os': platform.platform(), 'ruff': version('ruff'), 'jq': sha(Path(jq))})


def execute(argv: list[str], cwd: Path, output: Path) -> dict[str, Any]:
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'LC_ALL', 'SYSTEMROOT'}}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    start = time.perf_counter()
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=120, check=False)
    out, err = output.with_suffix('.stdout'), output.with_suffix('.stderr')
    out.write_bytes(result.stdout)
    err.write_bytes(result.stderr)
    return {'argv': argv, 'cwd': str(cwd), 'exit_code': result.returncode,
            'seconds': time.perf_counter() - start, 'stdout': out.name, 'stderr': err.name,
            'stdout_sha256': sha(out), 'stderr_sha256': sha(err)}


def bundle_contract(skill: Path) -> list[str]:
    errors = [f'Missing required input: {name}' for name in REQUIRED_FILES if not (skill / name).is_file()]
    try:
        parts = (skill / 'SKILL.md').read_text().split('---', 2)
        metadata = yaml.safe_load(parts[1])
        if metadata['name'] != 'sarif-parsing' or not isinstance(metadata['description'], str) or not metadata['description'].strip():
            errors.append('SARIF skill name and nonempty string description are required.')
    except (OSError, UnicodeError, IndexError, KeyError, TypeError, yaml.YAMLError) as exc:
        errors.append(f'Invalid SARIF metadata: {exc}')
    return errors


def report(skill: Path, project: Path, output: Path) -> tuple[list[dict[str, Any]], list[str]]:
    commands = [execute([sys.executable, '-c', REPORT_CODE, str(skill / 'resources'), str(output / 'scan.stdout')],
                        project, output / 'python-report')]
    errors = []
    if commands[-1]['exit_code']:
        errors.append('Python SARIF report failed.')
    else:
        actual = json.loads((output / 'python-report.stdout').read_bytes())
        diagnostics = json.loads((output / 'oracle.stdout').read_bytes())
        expected = {'total': len(diagnostics), 'by_level': {'error': len(diagnostics)} if diagnostics else {},
                    'by_rule': dict(Counter(d['code'] for d in diagnostics)),
                    'files_affected': len({d['filename'] for d in diagnostics}),
                    'rules_triggered': len({d['code'] for d in diagnostics})}
        if actual['summary'] != expected:
            errors.append('Python summary differs from the independent Ruff JSON result.')
        from urllib.parse import unquote, urlsplit
        actual_findings = sorted([r, level, unquote(urlsplit(path).path), line, message]
                                 for r, level, path, line, message in actual['findings'])
        expected_findings = sorted([d['code'], 'error', d['filename'], d['location']['row'], d['message']] for d in diagnostics)
        if actual_findings != expected_findings:
            errors.append('Python finding identities differ from Ruff JSON.')
    try:
        match = re.search(r"LEVEL_FN='\n(.*?)'\n", (skill / 'resources/jq-queries.md').read_text(), re.DOTALL)
        if match is None:
            errors.append('Documented jq severity function is missing.')
        else:
            program = match[1] + '\n[.runs[] as $run | $run.results[] | select(level($run) == "error")] | length'
            commands.append(execute(['jq', program, str(output / 'scan.stdout')], project, output / 'jq-report'))
            if commands[-1]['exit_code']:
                errors.append('Documented jq severity query failed.')
            elif json.loads((output / 'jq-report.stdout').read_bytes()) != len(json.loads((output / 'oracle.stdout').read_bytes())):
                errors.append('jq error count differs from Ruff JSON.')
    except (OSError, UnicodeError) as exc:
        errors.append(f'Cannot read jq query: {exc}')
    return commands, errors


def workflow(project: Path, skill: Path, output: Path, *, integrated: bool,
             trusted_revision: str | None = None, evidence_root: Path | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    commands = []
    checks = []
    gate: dict[str, Any] = {'state': 'not-requested', 'reuse': []}
    if integrated:
        from tracemantle import validate
        from tracemantle.bundle import create_manifest, manifest_from_dict
        from tracemantle.comparison import compare
        from tracemantle.evidence import evidence_from_dict
        from tracemantle.parser import DocumentSettings, parse
        from tracemantle.policy import load_trusted_policy

        settings = DocumentSettings(reference_format='skill-base-dir')
        gate_start = time.perf_counter()
        current_identity = input_identity(project)
        validation = validate(skill / 'SKILL.md', settings=settings)
        document = parse(skill / 'SKILL.md', settings=settings)
        manifest = create_manifest(skill, document=document)
        gate = {'state': 'unknown', 'reuse': [], 'manifest': manifest.to_dict(),
                'validation': [{'rule': d.rule, 'severity': d.severity.value, 'message': d.message} for d in validation.diagnostics]}
        if trusted_revision and evidence_root:
            policy = load_trusted_policy(evidence_root, trusted_revision, 'policy.toml')
            baseline = manifest_from_dict(json.loads((evidence_root / 'baseline.json').read_bytes()))
            records = tuple(evidence_from_dict(json.loads(p.read_bytes())) for p in sorted((evidence_root / 'records').glob('*.json')))
            decision = compare(baseline, manifest, records, policy)
            gate['comparison'] = decision.to_dict()
            gate['state'] = decision.state
            # An individual passing record cannot override incomplete overall coverage.
            compatible = all(c.configuration_sha256 == current_identity and c.checker_sha256 == sha(Path(__file__)) for c in policy.checks)
            gate['external_inputs_compatible'] = compatible
            if not compatible:
                gate['state'] = 'unknown'
            if decision.state == 'pass' and validation.valid and compatible:
                gate['reuse'] = [c.check_id for c in decision.checks if not c.rerun]
        gate['seconds'] = time.perf_counter() - gate_start
        (output / 'decision.json').write_text(json.dumps(gate, indent=2) + '\n')
    # Freeze the decision before executing either the task or its independent checker.
    for label, fmt in [('scan', 'sarif'), ('oracle', 'json')]:
        commands.append(execute([sys.executable, '-m', 'ruff', 'check', '--no-cache', '--output-format', fmt,
                                 'src', 'tests', 'scripts'], project, output / label))
        if commands[-1]['exit_code'] not in (0, 1):
            raise RuntimeError(f'Ruff infrastructure failure: {output / label}')
    for check in CHECKS:
        before = time.perf_counter()
        if check in gate['reuse']:
            checks.append({'id': check, 'reused': True, 'errors': [], 'seconds': time.perf_counter() - before})
            continue
        if check == 'bundle-contract':
            errors = bundle_contract(skill)
        elif check == 'report':
            report_commands, errors = report(skill, project, output)
            commands.extend(report_commands)
        else:
            (output / 'pytest.ini').write_text('[pytest]\n')
            command = execute([sys.executable, '-m', 'pytest', '-c', str(output / 'pytest.ini'), '-q', '-p', 'no:cacheprovider', '--import-mode=importlib',
                               '.'], skill / 'resources', output / 'upstream-tests')
            commands.append(command)
            errors = [] if command['exit_code'] == 0 else ['Upstream SARIF regression suite failed.']
        checks.append({'id': check, 'reused': False, 'errors': errors, 'seconds': time.perf_counter() - before})
    result = {'checks': checks, 'commands': commands, 'gate': gate, 'seconds': time.perf_counter() - start,
              'scan_exit': commands[0]['exit_code'], 'python': platform.python_version(), 'platform': platform.platform()}
    (output / 'run.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT)
    parser.add_argument('--skill', type=Path, default=SKILL)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--integrated', action='store_true')
    parser.add_argument('--trusted-revision')
    parser.add_argument('--evidence-root', type=Path)
    args = parser.parse_args()
    result = workflow(args.project.resolve(), args.skill.resolve(), args.output.resolve(), integrated=args.integrated,
                      trusted_revision=args.trusted_revision, evidence_root=args.evidence_root)
    print(json.dumps({'scan_exit': result['scan_exit'], 'checks': result['checks'], 'evidence_state': result['gate']['state']}))
    return int(result['scan_exit'] != 0 or any(c['errors'] for c in result['checks']))


if __name__ == '__main__':
    raise SystemExit(main())
