"""Print the two closeout behaviors from the installed or selected TraceMantle.

Run from a checkout root, which supplies only the fixture builders under
tests/. The CLI under test is whatever `python -m tracemantle` resolves to in
the running interpreter; its source path is printed first. Nothing here
executes skill content: the approved record is a synthetic policy control.

    python docs/verification/correctness-trust-closeout/reproduce.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

from tests.test_build_plan_product import _bundle, _record, _trusted_repository  # noqa: E402

BODIES = {
    'comment': '<!--\n~~~\n-->\n\n[helper](helper.py)',
    'div': '<div>\n```\n</div>\n\n[helper](helper.py)',
    'pre': '<pre>\n~~~\n</pre>\n[helper](helper.py)',
}
GIT = ('git', '-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid')


def cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', *args], capture_output=True, text=True, cwd=cwd, timeout=60)


def git(root: Path, *args: str) -> None:
    subprocess.run([*GIT, '-C', str(root), *args], check=True, capture_output=True)


def html_block(work: Path, name: str, body: str) -> dict[str, object]:
    base = _bundle(work / name / 'base')
    skill = base / 'SKILL.md'
    skill.write_text(skill.read_text().replace('Run [helper](helper.py).', body))
    record = _record(base)
    # Policy and evidence bind only SKILL.md, so the helper is governed only if discovery finds it.
    record = replace(record, inputs=tuple(item for item in record.inputs if item[0] == 'SKILL.md'),
                     observed_at=datetime.now(timezone.utc).isoformat())
    trusted = work / name / 'trusted'
    _trusted_repository(trusted, record)
    policy = trusted / 'pyproject.toml'
    policy.write_text(policy.read_text().replace('inputs=["SKILL.md", "helper.py"]', 'inputs=["SKILL.md"]'))
    git(trusted, 'add', '.')
    git(trusted, 'commit', '-qm', 'Declare only the skill input')
    revision = subprocess.check_output(['git', '-C', str(trusted), 'rev-parse', 'HEAD'], text=True).strip()
    manifest = json.loads(cli('manifest', str(base), '--format', 'json').stdout)['result']
    candidate = work / name / 'candidate'
    shutil.copytree(base, candidate)
    (candidate / 'helper.py').write_text('print("changed helper")\n')
    compared = cli('compare', str(base), str(candidate), '--trusted-root', str(trusted), '--base-revision', revision,
                   '--evidence', str(trusted / 'approved.json'), '--format', 'json')
    result = json.loads(compared.stdout)['result']
    return {'body': name, 'manifest_complete': manifest['complete'], 'dependencies': manifest['dependencies'],
            'compare_exit': compared.returncode, 'state': result['state'], 'changed_inputs': result['changed_inputs'],
            'required_reruns': result['required_reruns']}


def symlinked_configuration(work: Path) -> list[dict[str, object]]:
    root = work / 'repo'
    (root / 'hello').mkdir(parents=True)
    (root / 'config').mkdir()
    git(root, 'init', '-q')
    (root / 'hello' / 'SKILL.md').write_text(
        '---\nname: hello\ndescription: Use when reviewing changed configuration for a release.\n---\nOne.\nTwo.\nThree.\n')
    (root / 'config' / 'policy.toml').write_text('max-lines = 500\n')
    (root / 'tracemantle.toml').symlink_to('config/policy.toml')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    (root / 'config' / 'policy.toml').write_text('max-lines = 1\n')
    rows = []

    def row(label: str, *args: str) -> None:
        result = cli('hello', '--strict', '--format', 'json', *args, cwd=root)
        rows.append({'command': f'tracemantle hello --strict --format json {" ".join(args)}'.strip(), 'state': label,
                     'files_checked': json.loads(result.stdout)['files_checked'], 'exit': result.returncode})

    row('target edited, unstaged')
    row('target edited, unstaged', '--changed-since', 'HEAD')
    row('target edited, unstaged', '--changed-since', 'HEAD', '--config', 'tracemantle.toml')
    git(root, 'add', '.')
    row('target edited, staged', '--changed-since', 'HEAD')
    git(root, 'commit', '-qm', 'tighten the target')
    row('target edit committed', '--changed-since', 'HEAD~1')
    row('target edit committed', '--changed-since', 'HEAD')
    return rows


def main() -> None:
    import tracemantle

    print(json.dumps({'tracemantle': tracemantle.__version__, 'source': str(Path(tracemantle.__file__).parent),
                      'python': sys.version.split()[0]}))
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary).resolve()
        for name, body in BODIES.items():
            print(json.dumps(html_block(work, name, body)))
        for line in symlinked_configuration(work):
            print(json.dumps(line))


if __name__ == '__main__':
    main()
