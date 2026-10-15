"""First-use CLI contracts with real files and subprocesses."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tracemantle import __version__

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('path,strict,code,rule,line', [
    ('hello/SKILL.md', False, 0, None, None), ('invalid/SKILL.md', False, 1, 'parse.error', 3),
    ('missing/SKILL.md', False, 1, 'references.broken-link', 6), ('hello/', False, 0, None, None),
    ('warning/SKILL.md', False, 0, 'frontmatter.field.unknown', 4),
    ('warning/SKILL.md', True, 1, 'frontmatter.field.unknown', 4),
])
def test_first_use_text_and_json_contracts(tmp_path: Path, path: str, strict: bool, code: int, rule: str | None, line: int | None) -> None:
    shutil.copytree(ROOT / 'tests/fixtures/onboarding', tmp_path, dirs_exist_ok=True)
    command = [sys.executable, '-m', 'tracemantle', path, *(['--strict'] if strict else [])]
    text = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, encoding='utf-8')
    assert text.returncode == code and text.stderr == ''
    assert 'Checked 1 file:' in text.stdout and str(Path(path) / 'SKILL.md' if path.endswith('/') else Path(path)) in text.stdout
    guide = (ROOT / 'docs/getting-started.md').read_text(encoding='utf-8')
    skill_path = Path(path) / 'SKILL.md' if path.endswith('/') else Path(path)
    # The guide displays POSIX paths; the CLI deliberately renders native paths.
    assert text.stdout in guide.replace(skill_path.as_posix(), str(skill_path))
    result = subprocess.run([*command, '--format', 'json'], cwd=tmp_path, capture_output=True, text=True, encoding='utf-8')
    payload = json.loads(result.stdout)
    assert result.returncode == code and payload['schema_version'] == 2
    assert payload['gate'] == {'exit_code': code, 'passed': code == 0}
    assert payload['files_checked'] == 1 and len(payload['results']) == 1
    assert payload['results'][0]['valid'] == (not rule or rule == 'frontmatter.field.unknown')
    if rule:
        diagnostic = next(d for d in payload['results'][0]['diagnostics'] if d['rule'] == rule)
        assert diagnostic['line'] == line


def test_readme_and_help_put_basic_validation_first() -> None:
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert len(readme.split()) <= 350
    assert readme.count('\n## ') <= 5 and '<details>' not in readme
    assert readme.index(f'pip install tracemantle=={__version__}') < readme.index('## Optional evidence')
    result = subprocess.run([sys.executable, '-m', 'tracemantle', '--help'], capture_output=True, text=True, check=True)
    assert 'tracemantle SKILL.md' in result.stdout and 'No account or evidence policy needed' in result.stdout
    assert result.stdout.index('everyday validation:') < result.stdout.index('optional analysis, prompts and history:')
    assert '--ingest-critique' in result.stdout and '--approval-run-id' not in result.stdout


def test_neutral_export_example_runs_real_validation(tmp_path: Path) -> None:
    bundle = tmp_path / 'hello'
    shutil.copytree(ROOT / 'tests/fixtures/onboarding/hello', bundle)
    example = ROOT / 'docs/examples/export_validation.py'
    result = subprocess.run([sys.executable, '-I', str(example), str(bundle)], cwd=tmp_path, capture_output=True, check=True)
    export = json.loads(result.stdout)
    assert export['records'][0]['state'] == 'pass' and export['records'][0]['observation_method'] == 'static-analysis'
    (bundle / 'SKILL.md').write_text('---\nname: INVALID\n---\n')
    invalid = subprocess.run([sys.executable, '-I', str(example), str(bundle)], cwd=tmp_path, capture_output=True, check=True)
    assert json.loads(invalid.stdout)['records'][0]['state'] == 'fail'
