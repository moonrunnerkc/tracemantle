"""CLI regressions reproduced through a real ``python -m tracemantle`` subprocess."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL = '---\nname: demo-skill\ndescription: Use when checking command line regressions in a demo skill.\n---\n\nBody text.\n'


def _cli(*args: str, cwd: Path, stdin: bytes | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', *args], cwd=cwd, input=stdin,
                            capture_output=True, timeout=60)
    return subprocess.CompletedProcess(result.args, result.returncode, result.stdout.decode('utf-8'), result.stderr.decode('utf-8'))


def _skill(root: Path, name: str = 'demo-skill') -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text(SKILL.replace('demo-skill', name))
    return directory / 'SKILL.md'


def test_malformed_nested_pyproject_is_a_clean_configuration_error(tmp_path: Path) -> None:
    (tmp_path / 'tracemantle.toml').write_text('')
    skill = _skill(tmp_path / 'skills')
    (skill.parent / 'pyproject.toml').write_text('not = [toml\n')
    text = _cli('.', cwd=tmp_path)
    assert text.returncode == 2
    assert 'Traceback' not in text.stderr
    assert 'Invalid project TOML' in text.stderr
    envelope = _cli('.', '--format', 'json', cwd=tmp_path)
    assert envelope.returncode == 2
    report = json.loads(envelope.stdout)
    assert report['gate'] == {'passed': False, 'exit_code': 2}
    assert 'Invalid project TOML' in report['errors'][0]['error']

