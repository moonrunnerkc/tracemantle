"""Compare full and incremental scans on one seeded repository.

Usage: python benchmark_changed_since.py SRC_DIR OUTPUT.json [--skills N] [--repeats N]

SRC_DIR is the `src` directory of the TraceMantle checkout to measure. Git is
reached through a counting shim so each scenario also reports process counts.
Timings are wall-clock medians from this machine, not thresholds.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GIT = shutil.which('git') or 'git'


def git(root: Path, *args: str) -> None:
    subprocess.run([GIT, '-C', str(root), '-c', 'user.name=bench', '-c', 'user.email=bench@example.invalid', *args],
                   check=True, capture_output=True)


def seed(root: Path, count: int) -> None:
    root.mkdir(parents=True)
    git(root, 'init', '-q')
    for index in range(count):
        skill = root / 'skills' / f'skill-{index:04}'
        (skill / 'scripts').mkdir(parents=True)
        (skill / 'SKILL.md').write_text(
            f'---\nname: skill-{index:04}\ndescription: Use when measuring scan {index} for the benchmark.\n---\n'
            'Run [helper](scripts/helper.py).\nSecond line.\n')
        (skill / 'scripts' / 'helper.py').write_text(f'print({index})\n')
    (root / 'tracemantle.toml').write_text('max-lines = 500\n')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')


def run(src: Path, root: Path, shim: Path, log: Path, args: list[str], repeats: int) -> dict[str, object]:
    env = dict(os.environ, PYTHONPATH=str(src), PATH=f'{shim}{os.pathsep}{os.environ["PATH"]}', GIT_COUNT_LOG=str(log))
    timings, outcome = [], {}
    for _ in range(repeats):
        log.write_text('')
        started = time.perf_counter()
        result = subprocess.run([sys.executable, '-m', 'tracemantle', 'skills', '--format', 'json', '--strict', *args],
                                cwd=root, env=env, capture_output=True, text=True)
        timings.append(time.perf_counter() - started)
        report = json.loads(result.stdout)
        outcome = {'exit_code': result.returncode, 'selected': len(report['results']),
                   'failed': sum(not r['valid'] for r in report['results']),
                   'selected_paths_sha': hash_paths(report), 'git_processes': len(log.read_text().splitlines())}
    return {**outcome, 'median_seconds': round(statistics.median(timings), 4),
            'samples_seconds': [round(t, 4) for t in timings]}


def hash_paths(report: dict[str, list[dict[str, object]]]) -> str:
    import hashlib
    rows = sorted((str(r['path']), bool(r['valid']), len(r['diagnostics'])) for r in report['results'])  # type: ignore[arg-type]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('src', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--skills', type=int, default=500)
    parser.add_argument('--repeats', type=int, default=7)
    options = parser.parse_args()
    src = options.src.resolve()
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary).resolve()
        shim = work / 'shim'
        shim.mkdir()
        (shim / 'git').write_text(f'#!/bin/sh\necho x >> "$GIT_COUNT_LOG"\nexec "{GIT}" "$@"\n')
        (shim / 'git').chmod(0o755)
        log = work / 'git.log'
        root = work / 'repo'
        seed(root, options.skills)
        scenarios: dict[str, object] = {}

        def both(name: str, extra: tuple[str, ...] | list[str] = ()) -> None:
            scenarios[name] = {'full': run(src, root, shim, log, [*extra], options.repeats),
                               'incremental': run(src, root, shim, log, [*extra, '--changed-since', 'HEAD'], options.repeats)}

        both('no-changes')
        (root / 'skills/skill-0007/scripts/helper.py').write_text('print("changed")\n')
        both('one-changed-skill')
        git(root, 'checkout', '-q', '.')
        (root / 'tracemantle.toml').write_text('max-lines = 1\n')
        both('shared-config-change')
        git(root, 'checkout', '-q', '.')
        # A nested repository has its own project root, so the shared
        # configuration is selected explicitly for both scans.
        nested = root / 'skills' / 'nested'
        seed(nested, 50)
        (nested / 'skills/skill-0003/scripts/helper.py').write_text('print("changed")\n')
        both('nested-repository-one-change', ['--config', 'tracemantle.toml'])
    version = subprocess.run([sys.executable, '-c', 'import tracemantle; print(tracemantle.__version__)'],
                             env=dict(os.environ, PYTHONPATH=str(src)), capture_output=True, text=True).stdout.strip()
    options.output.write_text(json.dumps({
        'source': str(options.src), 'tracemantle_version': version, 'skills': options.skills, 'repeats': options.repeats,
        'python': platform.python_version(), 'platform': platform.platform(),
        'git': subprocess.run([GIT, '--version'], capture_output=True, text=True).stdout.strip(),
        'scenarios': scenarios}, indent=2) + '\n')


if __name__ == '__main__':
    main()
