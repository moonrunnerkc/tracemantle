"""Select the skills whose directories or effective configuration changed since a Git revision."""

from __future__ import annotations

import os
import subprocess
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from tracemantle.config_loader import CONFIG_NAMES, ConfigError, configs_in, is_discovery_boundary, text_selects_project_root
from tracemantle.io_limits import MAX_CONFIG_BYTES

# A changed-path listing past this size is not a pull-request diff; refuse it
# rather than hold an unbounded subprocess result.
_MAX_LISTING_BYTES = 16 * 1024 * 1024
# Git's error text is only quoted in a diagnostic; the rest is drained unread.
_MAX_STDERR_BYTES = 64 * 1024
_DEADLINE_SECONDS = 60.0
_GIT: tuple[str, ...] = ('git', '--no-pager', '--no-replace-objects')


class ChangeDetectionError(Exception):
    """The Git revision or working tree needed for --changed-since is unavailable."""


def _drain(stream: IO[bytes], kept: bytearray, limit: int, on_overflow: Callable[[], None]) -> None:
    """Keep at most ``limit`` bytes and discard the rest, so a child blocked on
    a full pipe always makes progress until it exits or is killed."""
    while chunk := stream.read(65536):
        room = limit - len(kept)
        if len(chunk) > room:
            on_overflow()
        kept += chunk[:room]


def _git(root: Path, *args: str, limit: int = _MAX_LISTING_BYTES) -> bytes:
    """Run one Git command in ``root`` and return its stdout.

    Both streams are bounded while they are read. A child that exceeds the
    stdout limit or the deadline is killed and reaped before the error is raised.

    Raises:
        ChangeDetectionError: Git cannot start, exits nonzero, runs past the
            deadline or writes more than ``limit`` bytes to stdout.
    """
    try:
        process = subprocess.Popen([*_GIT, '-C', str(root), *args], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    except OSError as exc:
        raise ChangeDetectionError(f'Cannot run git in {root}: {exc}. Install Git or drop --changed-since.') from exc
    assert process.stdout is not None and process.stderr is not None
    stdout, stderr = bytearray(), bytearray()
    overflow = threading.Event()

    def stop_child() -> None:
        overflow.set()
        process.kill()

    readers = [threading.Thread(target=_drain, args=(process.stdout, stdout, limit, stop_child), daemon=True),
               threading.Thread(target=_drain, args=(process.stderr, stderr, _MAX_STDERR_BYTES, lambda: None), daemon=True)]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=_DEADLINE_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        process.kill()
        process.wait()
        # End of file follows the child's exit. The bound covers a descendant
        # that inherited the pipes and is still holding them open.
        for reader in readers:
            reader.join(5)
        process.stdout.close()
        process.stderr.close()
    if overflow.is_set():
        raise ChangeDetectionError(f'git {args[0]} output in {root} exceeds {limit} bytes; validate without --changed-since.')
    if timed_out:
        raise ChangeDetectionError(f'git {args[0]} in {root} did not finish within {_DEADLINE_SECONDS:g} seconds; '
                                   'validate without --changed-since.')
    if process.returncode:
        detail = bytes(stderr).decode('utf-8', 'replace').strip() or f'exit {process.returncode}'
        raise ChangeDetectionError(f'git {args[0]} failed in {root}: {detail}')
    return bytes(stdout)


def _key(path: Path) -> str:
    """Compare paths the way the loosest supported file system does. Git may
    report a name in another Unicode form or case than the caller spelled it;
    treating two distinct paths as one only validates an extra skill."""
    return unicodedata.normalize('NFC', str(path)).casefold()


@dataclass(frozen=True, slots=True)
class _Changes:
    """One repository's differences between a commit and its working tree,
    with changed files and their ancestor directories held as ``_key`` values."""

    root: Path
    commit: str
    files: frozenset[str]
    directories: frozenset[str]


def _changes(root: Path, revision: str) -> _Changes:
    """Staged, unstaged, deleted and untracked (non-ignored) paths all count."""
    try:
        commit = _git(root, 'rev-parse', '--verify', '--quiet', f'{revision}^{{commit}}').decode().strip()
    except ChangeDetectionError as exc:
        raise ChangeDetectionError(f'--changed-since {revision!r} does not name a commit in {root}; fetch it or pick another revision.') from exc
    tracked = _git(root, 'diff', '--name-only', '--no-renames', '-z', commit, '--')
    untracked = _git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--')
    files = [root / name.decode('utf-8', 'surrogateescape') for name in (tracked + untracked).split(b'\0') if name]
    return _Changes(root, commit, frozenset(map(_key, files)),
                    frozenset(_key(parent) for path in files for parent in path.parents))


def _toplevel(directory: Path) -> Path:
    return Path(_git(directory, 'rev-parse', '--show-toplevel').decode('utf-8', 'surrogateescape').strip()).resolve()


def _repository_root(directory: Path, roots: dict[Path, Path]) -> Path:
    """Return the work tree containing ``directory``, asking Git once per tree.

    Git finds a repository by walking up to the nearest ``.git`` entry, which
    is a directory in a clone and a file in a worktree or submodule. The same
    walk here names a candidate, and Git confirms it. Every directory between
    is then inside that tree by Git's own rule, not by path prefix, because a
    nested repository would have supplied a nearer ``.git``. Anything unusual
    is answered by Git for that directory alone.
    """
    if 'GIT_DIR' in os.environ or 'GIT_WORK_TREE' in os.environ:
        return _toplevel(directory)
    walked = []
    for candidate in (directory, *directory.parents):
        if candidate in roots:
            root = roots[candidate]
            break
        walked.append(candidate)
        if (candidate / '.git').exists():
            root = _toplevel(candidate)
            if root != candidate:
                return _toplevel(directory)
            break
    else:
        return _toplevel(directory)
    roots.update(dict.fromkeys(walked, root))
    return root


def _baseline_blob(changes: _Changes, path: Path) -> bytes | None:
    """Return ``path`` as committed at the baseline, or None if it is absent there."""
    try:
        return _git(changes.root, 'cat-file', 'blob', f'{changes.commit}:{path.relative_to(changes.root).as_posix()}',
                    limit=MAX_CONFIG_BYTES)
    except ChangeDetectionError:
        return None


def _applies_differently(changes: _Changes, path: Path, present: bool) -> bool:
    """Whether the configuration file ``path`` cannot be shown to apply to its
    directory exactly as it did at the baseline."""
    if _key(path) not in changes.files:
        # Git reports no difference. That establishes nothing for a file it
        # ignores, which has no baseline to compare with.
        return present and _baseline_blob(changes, path) is None
    if present:
        return True
    raw = _baseline_blob(changes, path)
    if raw is None:
        return False  # A changed pyproject.toml that never carried a tool table.
    try:
        return text_selects_project_root(path, raw.decode('utf-8'))
    except (ConfigError, UnicodeDecodeError):
        return True  # An unreadable baseline cannot be ruled out.


def _changed_config(directory: Path, changes: _Changes, cache: dict[Path, Path | None]) -> Path | None:
    """Return a configuration file that applies to ``directory`` now, or
    applied at the baseline, and cannot be shown unchanged. The walk follows
    configuration discovery: it ends at the nearest directory holding
    unchanged configuration, or at the discovery boundary."""
    visited = []
    result: Path | None = None
    for current in (directory, *directory.parents):
        if current in cache:
            result = cache[current]
            break
        visited.append(current)
        present = configs_in(current)
        result = next((path for path in (current / name for name in CONFIG_NAMES)
                       if _applies_differently(changes, path, path in present)), None)
        if result or present or current == changes.root or is_discovery_boundary(current):
            break
    cache.update(dict.fromkeys(visited, result))
    return result


def changed_skills(paths: list[Path], revision: str, *, explicit_config: Path | None = None,
                   notify: Callable[[str], None] = lambda message: None) -> list[Path]:
    """Return the SKILL.md paths that need validation since ``revision``, in
    the given order.

    A change anywhere under a skill's directory counts, including helpers and
    nested resources, because the bundle includes them. So does a created,
    edited, deleted or renamed configuration file that applies to the skill now
    or applied at ``revision``. Each skill is checked against the changes of
    its own repository. With ``explicit_config``, that file replaces discovered
    configuration: if it changed, or has no history at ``revision`` in the
    repository that contains it, every skill is returned. ``notify`` receives one
    message per reason that widened the selection.

    The selection covers file changes only. It does not show that an
    unselected skill passes under a different tool version, environment or
    command-line policy.

    Raises:
        ChangeDetectionError: ``revision`` starts with ``-``, a path is not in
            a Git work tree, the revision does not name a commit, or git fails.
        ConfigError: a ``pyproject.toml`` on a skill's configuration path
            cannot be read or parsed.
    """
    if not revision or revision.startswith('-'):
        raise ChangeDetectionError(f'--changed-since needs a revision such as origin/main, not {revision!r}.')
    roots: dict[Path, Path] = {}
    changes: dict[Path, _Changes] = {}
    configs: dict[Path, Path | None] = {}
    notified: set[Path] = set()
    everything = explicit_config is not None and _explicit_config_changed(explicit_config.resolve(), revision, roots, changes, notify)
    selected = []
    for path in paths:
        directory = path.resolve().parent
        root = _repository_root(directory, roots)
        if root not in changes:
            changes[root] = _changes(root, revision)
        found = changes[root]
        if everything or _key(directory) in found.directories:
            selected.append(path)
            continue
        if explicit_config is not None:
            continue
        config = _changed_config(directory, found, configs)
        if config is None:
            continue
        selected.append(path)
        if config not in notified:
            notified.add(config)
            state = 'changed since' if _key(config) in found.files else 'has no history at'
            notify(f'Configuration {config.relative_to(root).as_posix()} {state} {revision}; validating the skills it applies to.')
    return selected


def _explicit_config_changed(config: Path, revision: str, roots: dict[Path, Path], changes: dict[Path, _Changes],
                             notify: Callable[[str], None]) -> bool:
    """Compare a ``--config`` file with ``revision`` in its own repository.
    A file with no committed baseline there cannot be shown unchanged."""
    try:
        root = _repository_root(config.parent, roots)
        if root not in changes:
            changes[root] = _changes(root, revision)
        found = changes[root]
        if _key(config) in found.files:
            notify(f'Configuration {config.name} changed since {revision}; validating every skill.')
            return True
        _git(root, 'cat-file', '-e', f'{found.commit}:{config.relative_to(root).as_posix()}')
        return False
    except ChangeDetectionError:
        notify(f'Configuration {config.name} has no history at {revision}; validating every skill.')
        return True
