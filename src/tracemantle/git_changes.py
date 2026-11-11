"""Select the skills whose directories changed since a Git revision."""

from __future__ import annotations

import subprocess
from pathlib import Path

# A changed-path listing past this size is not a pull-request diff; refuse it
# rather than hold an unbounded subprocess result.
_MAX_LISTING_BYTES = 16 * 1024 * 1024


class ChangeDetectionError(Exception):
    """The Git revision or working tree needed for --changed-since is unavailable."""


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(['git', '--no-pager', '--no-replace-objects', '-C', str(root), *args],
                                capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ChangeDetectionError(f'Cannot run git in {root}: {exc}. Install Git or drop --changed-since.') from exc
    if result.returncode:
        detail = result.stderr.decode('utf-8', 'replace').strip() or f'exit {result.returncode}'
        raise ChangeDetectionError(f'git {args[0]} failed in {root}: {detail}')
    if len(result.stdout) > _MAX_LISTING_BYTES:
        raise ChangeDetectionError(f'git {args[0]} output in {root} exceeds {_MAX_LISTING_BYTES} bytes; validate without --changed-since.')
    return result.stdout


def _changed_directories(root: Path, revision: str) -> frozenset[Path]:
    """Every directory containing a change between ``revision`` and the working
    tree, at any depth: staged, unstaged, deleted and untracked (non-ignored)
    files all count."""
    try:
        commit = _git(root, 'rev-parse', '--verify', '--quiet', f'{revision}^{{commit}}').decode().strip()
    except ChangeDetectionError as exc:
        raise ChangeDetectionError(f'--changed-since {revision!r} does not name a commit in {root}; fetch it or pick another revision.') from exc
    tracked = _git(root, 'diff', '--name-only', '--no-renames', '-z', commit, '--')
    untracked = _git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--')
    directories: set[Path] = set()
    for name in (tracked + untracked).split(b'\0'):
        if name:
            directories.update((root / name.decode('utf-8', 'surrogateescape')).parents)
    return frozenset(directories)


def changed_skills(paths: list[Path], revision: str) -> list[Path]:
    """Return the SKILL.md paths whose skill directory contains any change
    since ``revision``, in the given order.

    A change anywhere under a skill's directory counts, including helpers and
    nested resources, because the bundle includes them. Each skill is checked
    against the changes of its own repository.

    Raises:
        ChangeDetectionError: ``revision`` starts with ``-``, a path is not in
            a Git work tree, the revision does not name a commit, or git fails.
    """
    if not revision or revision.startswith('-'):
        raise ChangeDetectionError(f'--changed-since needs a revision such as origin/main, not {revision!r}.')
    roots: dict[Path, Path] = {}
    changes: dict[Path, frozenset[Path]] = {}
    selected = []
    for path in paths:
        directory = path.resolve().parent
        if directory not in roots:
            roots[directory] = Path(_git(directory, 'rev-parse', '--show-toplevel').decode('utf-8', 'surrogateescape').strip()).resolve()
        root = roots[directory]
        if root not in changes:
            changes[root] = _changed_directories(root, revision)
        if directory in changes[root]:
            selected.append(path)
    return selected
