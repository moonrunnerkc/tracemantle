"""Check-specific identity and evidence for the maintainer SARIF workflow only."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path
from typing import Any

ELIGIBLE = ('bundle-contract', 'upstream-tests')
ROOT = Path(__file__).resolve().parents[1]
SCOPES = ROOT / 'integrations/sarif/check-scopes.json'


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def file_identity(path: Path) -> tuple[str, bool]:
    return hashlib.sha256(path.read_bytes()).hexdigest(), bool(path.stat().st_mode & 0o111)


def execution_identity() -> dict[str, Any]:
    """Measure installed bytes rather than trusting version strings alone."""
    stdlib = Path(sysconfig.get_path('stdlib'))
    files = {}
    for directory, dirs, names in os.walk(stdlib):
        dirs[:] = sorted(d for d in dirs if d not in {'site-packages', 'dist-packages', 'test', 'tests'})
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix in {'.py', '.pyc', '.so'}:
                files[str(path.relative_to(stdlib))] = file_identity(path)
    packages = {}
    for name in ('PyYAML', 'pytest', 'pluggy', 'iniconfig', 'packaging', 'pygments'):
        dist = importlib.metadata.distribution(name)
        packages[name] = {'version': dist.version, 'files': {
            str(p): file_identity(Path(str(dist.locate_file(p)))) for p in dist.files or ()
            if str(p).endswith(('.py', '.pyc', '.so'))}}
    jq = shutil.which('jq')
    if jq is None:
        raise RuntimeError('jq is required')
    libraries = {}
    for binary in (Path(sys.executable).resolve(), Path(jq).resolve()):
        libraries[binary.name] = file_identity(binary)
        # This Linux deployment binds native dependencies too. Other hosts rerun.
        linked = subprocess.run(['ldd', str(binary)], capture_output=True, text=True, check=True)
        for line in linked.stdout.splitlines():
            for word in line.split():
                if word.startswith('/'):
                    path = Path(word)
                    libraries[path.name] = file_identity(path)
    return {'python': sys.version, 'os': platform.platform(), 'stdlib': digest(files),
            'packages': packages, 'native': libraries,
            'environment': {'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'PYTHONHASHSEED': '0',
                            'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                            'HOME': 'fresh-output',
                            'PATH': 'resolved-jq-directory plus os.defpath'},
            'pytest': ['--basetemp=fresh-output/pytest-temp', '--noconftest', '-p', 'no:cacheprovider', '--import-mode=importlib', 'test_sarif_helpers.py']}


def identities(skill: Path) -> tuple[dict[str, Any], list[str]]:
    scopes = json.loads(SCOPES.read_bytes())
    context = execution_identity()
    checker = digest({p: file_identity(ROOT / 'scripts' / p) for p in ('sarif_workflow.py', 'sarif_reuse.py')})
    unexpected = [str(p.relative_to(skill)) for p in (skill / 'resources').rglob('*')
                  if p.is_file() and p.suffix in {'.py', '.so', '.pth'}
                  and str(p.relative_to(skill)) not in scopes['upstream-tests']['inputs']]
    values = {}
    for check in ELIGIBLE:
        scope = scopes[check]
        selected = {p: file_identity(skill / p) if (skill / p).is_file() and not (skill / p).is_symlink() else None
                    for p in scope['inputs']}
        environment = dict(context)
        if check == 'bundle-contract':
            environment['packages'] = {'PyYAML': context['packages']['PyYAML']}
            environment.pop('pytest')
            environment['native'] = {k: v for k, v in context['native'].items() if k != 'jq'}
        config = digest({'execution': environment, 'checker_files': checker, 'dialect': 'skill-base-dir'})
        profile = hashlib.sha256((json.dumps(scope, sort_keys=True, indent=2) + '\n').encode()).hexdigest()
        values[check] = {'inputs': selected, 'configuration_sha256': config, 'profile_sha256': profile,
                         'key': digest({'inputs': selected, 'configuration': config, 'scope': profile}),
                         'scope': scope}
    return values, unexpected


def decide(skill: Path, evidence_root: Path, revision: str | None, mechanism: str) -> dict[str, Any]:
    started = time.perf_counter()
    values, unexpected = identities(skill)
    result: dict[str, Any] = {'state': 'unknown', 'reuse': [], 'identities': values, 'unresolved': unexpected}
    if mechanism == 'cache':
        cache_path = evidence_root / 'cache.json'
        cache = json.loads(cache_path.read_bytes()) if cache_path.exists() else {}
        result['reuse'] = [c for c in ELIGIBLE if cache.get(c) == values[c]['key'] and not (c == 'upstream-tests' and unexpected)]
        result['state'] = 'pass' if len(result['reuse']) == len(ELIGIBLE) else 'unknown'
    else:
        from tracemantle import validate
        from tracemantle.bundle import create_manifest, manifest_from_dict
        from tracemantle.comparison import compare
        from tracemantle.evidence import evidence_from_dict
        from tracemantle.parser import DocumentSettings, parse
        from tracemantle.policy import load_trusted_policy
        from tracemantle.storage import read_json

        if revision is None:
            raise ValueError('TraceMantle reuse requires an explicit trusted revision')
        settings = DocumentSettings(reference_format='skill-base-dir')
        validation = validate(skill / 'SKILL.md', settings=settings)
        manifest = create_manifest(skill, document=parse(skill / 'SKILL.md', settings=settings))
        policy = load_trusted_policy(evidence_root, revision, 'policy.toml')
        records = tuple(evidence_from_dict(read_json(p)) for p in sorted((evidence_root / 'records').glob('*.json')))
        comparison = compare(manifest_from_dict(read_json(evidence_root / 'baseline.json')), manifest, records, policy)
        result.update(comparison=comparison.to_dict(), validation=[{'rule': d.rule, 'severity': d.severity.value, 'message': d.message} for d in validation.diagnostics],
                      manifest=manifest.to_dict(), state=comparison.state)
        checks = {c.id: c for c in policy.checks}
        if validation.valid:
            result['reuse'] = [c.check_id for c in comparison.checks if not c.rerun and c.check_id in ELIGIBLE and not (c.check_id == 'upstream-tests' and unexpected)
                               and checks[c.check_id].configuration_sha256 == values[c.check_id]['configuration_sha256']
                               and checks[c.check_id].profile_sha256 == values[c.check_id]['profile_sha256']]
    result['seconds'] = time.perf_counter() - started
    return result
