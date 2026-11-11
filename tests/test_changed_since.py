"""--changed-since selects skills from a real Git repository's changes."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tracemantle.git_changes import ChangeDetectionError, changed_skills

pytestmark = pytest.mark.skipif(shutil.which('git') is None, reason='requires git')


def _git(root: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid', *args],
                   check=True, capture_output=True)


def _repository(root: Path) -> dict[str, Path]:
    root.mkdir()
    _git(root, 'init', '-q')
    skills = {}
    for name in ('alpha-skill', 'beta-skill', 'gamma-skill'):
        (root / name / 'scripts').mkdir(parents=True)
        (root / name / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Use when testing change selection.\n---\nBody\n')
        (root / name / 'scripts' / 'helper.py').write_text('print("v1")\n')
        skills[name] = root / name / 'SKILL.md'
    (root / '.gitignore').write_text('*.log\n')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    return skills


def test_helper_edits_deletions_and_untracked_files_select_their_skill(tmp_path: Path) -> None:
    skills = _repository(tmp_path / 'repo')
    paths = list(skills.values())
    assert changed_skills(paths, 'HEAD') == []
    (skills['alpha-skill'].parent / 'scripts' / 'helper.py').write_text('print("v2")\n')
    (skills['beta-skill'].parent / 'scripts' / 'helper.py').unlink()
    (skills['gamma-skill'].parent / 'debug.log').write_text('ignored by .gitignore\n')
    assert changed_skills(paths, 'HEAD') == [skills['alpha-skill'], skills['beta-skill']]
    (skills['gamma-skill'].parent / 'notes.md').write_text('new untracked file\n')
    assert changed_skills(paths, 'HEAD') == paths


def test_committed_changes_since_an_older_revision_count(tmp_path: Path) -> None:
    skills = _repository(tmp_path / 'repo')
    (skills['beta-skill']).write_text(skills['beta-skill'].read_text() + '\nMore.\n')
    _git(tmp_path / 'repo', 'commit', '-qam', 'edit beta')
    assert changed_skills(list(skills.values()), 'HEAD~1') == [skills['beta-skill']]
    assert changed_skills(list(skills.values()), 'HEAD') == []


@pytest.mark.parametrize('revision,message', [('-p', 'needs a revision'), ('no-such-ref', 'does not name a commit')])
def test_unusable_revisions_are_refused(tmp_path: Path, revision: str, message: str) -> None:
    skills = _repository(tmp_path / 'repo')
    with pytest.raises(ChangeDetectionError, match=message):
        changed_skills(list(skills.values()), revision)


def test_paths_outside_a_work_tree_are_refused(tmp_path: Path) -> None:
    skill = tmp_path / 'loose' / 'SKILL.md'
    skill.parent.mkdir()
    skill.write_text('---\nname: loose\ndescription: d\n---\n')
    with pytest.raises(ChangeDetectionError, match='rev-parse failed'):
        changed_skills([skill], 'HEAD')


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', *args], cwd=root, capture_output=True, text=True, timeout=60)


def test_cli_validates_only_changed_skills_and_passes_when_none_changed(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    skills = _repository(root)
    unchanged = _cli(root, '.', '--changed-since', 'HEAD', '--format', 'json')
    assert unchanged.returncode == 0
    assert json.loads(unchanged.stdout)['results'] == []
    assert 'No skills changed since HEAD' in unchanged.stderr
    skills['gamma-skill'].write_text('---\nname: Wrong_Name\ndescription: Use when testing.\n---\n')
    changed = _cli(root, '.', '--changed-since', 'HEAD', '--format', 'json')
    assert changed.returncode == 1
    assert [Path(r['path']) for r in json.loads(changed.stdout)['results']] == [Path('gamma-skill/SKILL.md')]


def test_cli_rejects_changed_since_with_single_skill_modes(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    _repository(root)
    result = _cli(root, '.', '--changed-since', 'HEAD', '--show-history')
    assert result.returncode == 2
    assert 'Cannot use --changed-since with --show-history' in result.stderr
