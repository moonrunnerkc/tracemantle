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


LONG_BODY = 'Line one.\nLine two.\nLine three.\n'


def _configured(root: Path, config_name: str = 'tracemantle.toml', config: str = 'max-lines = 500\n') -> dict[str, Path]:
    """A committed repository whose skills pass under the committed configuration."""
    skills = _repository(root)
    for path in skills.values():
        path.write_text(path.read_text().replace('Body\n', LONG_BODY))
    (root / config_name).write_text(config)
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'configured baseline')
    return skills


def _selected(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [Path(r['path']).parent.name for r in json.loads(result.stdout)['results']]


ALL = ['alpha-skill', 'beta-skill', 'gamma-skill']


def test_tightened_shared_configuration_selects_every_skill(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    _configured(root)
    assert _cli(root, '.', '--strict', '--changed-since', 'HEAD').returncode == 0
    (root / 'tracemantle.toml').write_text('max-lines = 1\n')
    full = _cli(root, '.', '--strict', '--format', 'json')
    incremental = _cli(root, '.', '--strict', '--changed-since', 'HEAD', '--format', 'json')
    assert full.returncode == incremental.returncode == 1
    assert _selected(incremental) == _selected(full) == ALL
    assert json.loads(incremental.stdout)['results'] == json.loads(full.stdout)['results']
    assert 'tracemantle.toml changed since HEAD' in incremental.stderr


@pytest.mark.parametrize('state', ['unstaged', 'staged', 'committed'])
def test_configuration_edits_count_in_every_git_state(tmp_path: Path, state: str) -> None:
    root = tmp_path / 'repo'
    _configured(root)
    baseline = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    (root / 'tracemantle.toml').write_text('max-lines = 1\n')
    if state != 'unstaged':
        _git(root, 'add', '.')
    if state == 'committed':
        _git(root, 'commit', '-qm', 'tighten')
        assert _selected(_cli(root, '.', '--changed-since', 'HEAD', '--format', 'json')) == []
    assert _selected(_cli(root, '.', '--changed-since', baseline, '--format', 'json')) == ALL


@pytest.mark.parametrize('change', ['add-untracked', 'delete', 'rename', 'add-nearer', 'add-legacy', 'pyproject-namespace'])
def test_configuration_creation_deletion_and_precedence_changes_select_skills(tmp_path: Path, change: str) -> None:
    root = tmp_path / 'repo'
    skills = _configured(root, config='max-lines = 2\n' if change in {'delete', 'rename'} else 'max-lines = 500\n')
    expected = ALL
    if change == 'add-untracked':
        (root / 'tracemantle.toml').unlink()
        _git(root, 'commit', '-qam', 'no configuration')
        (root / 'tracemantle.toml').write_text('max-lines = 1\n')
    elif change == 'delete':
        (root / 'tracemantle.toml').unlink()
    elif change == 'rename':
        _git(root, 'mv', 'tracemantle.toml', 'skillcheck.toml')
    elif change == 'add-nearer':
        (skills['beta-skill'].parent / 'tracemantle.toml').write_text('max-lines = 1\n')
        expected = ['beta-skill']
    elif change == 'add-legacy':
        (root / 'skillcheck.toml').write_text('max-tokens = 1\n')
    else:
        (root / 'pyproject.toml').write_text('[tool.tracemantle]\nmax-lines = 1\n')
    result = _cli(root, *(['beta-skill'] if change == 'add-nearer' else ['.']), '--changed-since', 'HEAD', '--format', 'json')
    assert _selected(result) == expected
    if change == 'add-nearer':
        # The other skills keep the unchanged root configuration.
        assert changed_skills([skills['alpha-skill'], skills['gamma-skill']], 'HEAD') == []


def test_pyproject_edits_outside_the_tool_namespace_are_not_configuration(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    skills = _repository(root)
    (root / 'pyproject.toml').write_text('[project]\nname = "demo"\nversion = "1"\n')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'package metadata')
    (root / 'pyproject.toml').write_text('[project]\nname = "demo"\nversion = "2"\n')
    assert changed_skills(list(skills.values()), 'HEAD') == []
    (root / 'pyproject.toml').write_text('[project]\nname = "demo"\nversion = "2"\n\n[tool.tracemantle]\nmax-lines = 1\n')
    assert changed_skills(list(skills.values()), 'HEAD') == list(skills.values())
    _git(root, 'commit', '-qam', 'adopt configuration')
    (root / 'pyproject.toml').write_text('[project]\nname = "demo"\nversion = "2"\n')
    assert changed_skills(list(skills.values()), 'HEAD') == list(skills.values())


def test_unchanged_nearer_configuration_shields_a_skill_from_root_changes(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    skills = _repository(root)
    (root / 'tracemantle.toml').write_text('max-lines = 500\n')
    (skills['beta-skill'].parent / 'tracemantle.toml').write_text('max-lines = 400\n')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'two project roots')
    (root / 'tracemantle.toml').write_text('max-lines = 1\n')
    assert changed_skills([skills['beta-skill']], 'HEAD') == []
    assert changed_skills([skills['alpha-skill']], 'HEAD') == [skills['alpha-skill']]


def test_explicit_configuration_is_compared_or_forces_a_full_scan(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    _configured(root, config_name='ci.toml')
    args = ('.', '--strict', '--config', 'ci.toml', '--changed-since', 'HEAD', '--format', 'json')
    assert _selected(_cli(root, *args)) == []
    (root / 'ci.toml').write_text('max-lines = 1\n')
    changed = _cli(root, *args)
    assert changed.returncode == 1 and _selected(changed) == ALL
    _git(root, 'checkout', '-q', 'ci.toml')
    external = tmp_path / 'external.toml'
    external.write_text('max-lines = 1\n')
    outside = _cli(root, '.', '--strict', '--config', str(external), '--changed-since', 'HEAD', '--format', 'json')
    assert outside.returncode == 1 and _selected(outside) == ALL
    assert 'has no history at HEAD' in outside.stderr and 'validating every skill' in outside.stderr
    (root / 'local.log').write_text('max-lines = 500\n')
    ignored = _cli(root, '.', '--config', 'local.log', '--changed-since', 'HEAD', '--format', 'json')
    assert _selected(ignored) == ALL and 'has no history at HEAD' in ignored.stderr


@pytest.mark.parametrize('args,text', [
    (('--config', 'missing.toml'), 'missing.toml'),
    ((), 'Cannot parse'),
])
def test_missing_or_malformed_configuration_is_a_configuration_error(tmp_path: Path, args: tuple[str, ...], text: str) -> None:
    root = tmp_path / 'repo'
    _configured(root)
    if not args:
        (root / 'tracemantle.toml').write_text('max-lines = \n')
    result = _cli(root, '.', *args, '--changed-since', 'HEAD', '--format', 'json')
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report['gate'] == {'passed': False, 'exit_code': 2} and text in report['errors'][0]['error']


def test_nested_repositories_and_worktrees_use_their_own_changes(tmp_path: Path) -> None:
    outer = tmp_path / 'outer'
    skills = _repository(outer)
    (outer / 'tracemantle.toml').write_text('max-lines = 500\n')
    _git(outer, 'add', '.')
    _git(outer, 'commit', '-qm', 'configure outer')
    inner = _repository(outer / 'vendor')
    worktree = tmp_path / 'worktree'
    _git(outer, 'worktree', 'add', '-q', str(worktree), 'HEAD')
    linked = worktree / 'alpha-skill' / 'SKILL.md'
    paths = [*skills.values(), *inner.values(), linked]
    # The nested repository is one untracked directory to the outer repository,
    # and an outer change is not a change to the nested or linked work trees.
    assert changed_skills(paths, 'HEAD') == []
    (outer / 'tracemantle.toml').write_text('max-lines = 1\n')
    assert changed_skills(paths, 'HEAD') == list(skills.values())
    _git(outer, 'checkout', '-q', 'tracemantle.toml')
    (inner['beta-skill'].parent / 'scripts' / 'helper.py').write_text('print("v2")\n')
    (linked.parent / 'notes.md').write_text('note\n')
    assert changed_skills(paths, 'HEAD') == [inner['beta-skill'], linked]


def test_submodule_skills_follow_the_submodule_history(tmp_path: Path) -> None:
    library = tmp_path / 'library'
    _repository(library)
    parent = tmp_path / 'parent'
    parent.mkdir()
    _git(parent, 'init', '-q')
    _git(parent, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(library), 'skills')
    (parent / 'tracemantle.toml').write_text('max-lines = 500\n')
    _git(parent, 'add', '.')
    _git(parent, 'commit', '-qm', 'add skills')
    skill = parent / 'skills' / 'alpha-skill' / 'SKILL.md'
    assert changed_skills([skill], 'HEAD') == []
    # The parent's configuration sits above the submodule root, where
    # configuration discovery stops, so it does not apply to the submodule.
    (parent / 'tracemantle.toml').write_text('max-lines = 1\n')
    assert changed_skills([skill], 'HEAD') == []
    (skill.parent / 'scripts' / 'helper.py').write_text('print("v2")\n')
    assert changed_skills([skill], 'HEAD') == [skill]


def test_one_repository_is_discovered_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tracemantle.git_changes as git_changes

    skills = _repository(tmp_path / 'repo')
    calls: list[tuple[str, ...]] = []
    real = git_changes._git

    def counting(root: Path, *args: str, **kwargs: int) -> bytes:
        calls.append(args)
        return real(root, *args, **kwargs)

    monkeypatch.setattr(git_changes, '_git', counting)
    assert changed_skills(list(skills.values()), 'HEAD') == []
    assert sum(args[:2] == ('rev-parse', '--show-toplevel') for args in calls) == 1
    assert len(calls) == 4


def test_oversized_git_output_stops_the_child(tmp_path: Path) -> None:
    import tracemantle.git_changes as git_changes

    skills = _repository(tmp_path / 'repo')
    for index in range(200):
        (tmp_path / 'repo' / f'untracked-file-with-a-long-name-{index:04}.txt').write_text('x')
    with pytest.raises(ChangeDetectionError, match='exceeds 1024 bytes'):
        git_changes._git(tmp_path / 'repo', 'ls-files', '--others', '--exclude-standard', '-z', '--', limit=1024)
    assert changed_skills(list(skills.values()), 'HEAD') == []


def test_a_child_that_keeps_running_is_terminated_at_the_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    import tracemantle.git_changes as git_changes

    script = tmp_path / 'slow.py'
    script.write_text('import sys, time\nsys.stderr.write("e" * 300000)\nsys.stderr.flush()\ntime.sleep(60)\n')
    monkeypatch.setattr(git_changes, '_GIT', (sys.executable, str(script)))
    monkeypatch.setattr(git_changes, '_DEADLINE_SECONDS', 1.0)
    started = time.monotonic()
    with pytest.raises(ChangeDetectionError, match='did not finish'):
        git_changes._git(tmp_path, 'diff')
    assert time.monotonic() - started < 20


def test_ignored_discovered_configuration_cannot_be_shown_unchanged(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    skills = _repository(root)
    (root / '.gitignore').write_text('*.log\ntracemantle.toml\n')
    _git(root, 'commit', '-qam', 'ignore local configuration')
    assert changed_skills(list(skills.values()), 'HEAD') == []
    # Git reports nothing for an ignored file, so its content has no baseline.
    (root / 'tracemantle.toml').write_text('max-lines = 1\n')
    notes: list[str] = []
    assert changed_skills(list(skills.values()), 'HEAD', notify=notes.append) == list(skills.values())
    assert len(notes) == 1 and 'tracemantle.toml has no history at HEAD' in notes[0]


def test_changed_paths_match_regardless_of_unicode_form_or_case(tmp_path: Path) -> None:
    import unicodedata

    root = tmp_path / 'repo'
    _repository(root)
    name = unicodedata.normalize('NFD', 'café-skill')
    (root / name).mkdir()
    skill = root / name / 'SKILL.md'
    skill.write_text('---\nname: cafe-skill\ndescription: Use when testing path forms.\n---\nBody\n')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'accented directory')
    skill.write_text(skill.read_text() + 'More.\n')
    listed = next(path for path in root.iterdir() if path.name.endswith('-skill') and not path.name.isascii()) / 'SKILL.md'
    for form in ('NFC', 'NFD'):
        spelled = listed.parent.with_name(unicodedata.normalize(form, listed.parent.name)) / 'SKILL.md'
        if spelled.exists():
            assert changed_skills([spelled], 'HEAD') == [spelled]
    (root / 'alpha-skill' / 'notes.md').write_text('note\n')
    shouted = root / 'ALPHA-SKILL' / 'SKILL.md'
    if shouted.exists():  # Case-insensitive file systems only.
        assert changed_skills([shouted], 'HEAD') == [shouted]
