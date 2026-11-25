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
_LINK_UNPROVEN = 'is reached through a symbolic link and cannot be shown unchanged since'
_MAX_LINK_HOPS = 40  # The usual kernel limit; a longer chain is treated as a cycle.


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


def _in_history(changes: _Changes, path: Path, kind: str) -> bool:
    """Whether ``path`` is a ``kind`` object (blob or tree) at the baseline.
    A symbolic link is recorded as a blob."""
    if path == changes.root:
        return kind == 'tree'
    try:
        found = _git(changes.root, 'cat-file', '-t', f'{changes.commit}:{path.relative_to(changes.root).as_posix()}', limit=64)
    except ChangeDetectionError:
        return False
    return found.strip() == kind.encode()


def _resolves_unchanged(start: Path, parts: tuple[str, ...], history: Callable[[Path], _Changes], spelled: bool) -> bool:
    """Whether following ``parts`` from the resolved directory ``start``
    reaches a file that can be shown to be the one they reached at the baseline.

    The path is resolved one component at a time, as the kernel does, and Git
    must vouch for each step it cannot infer. A symbolic link must be committed
    and unchanged in the repository that holds it, since Git records its text.
    A directory left through ".." must have existed at the baseline, which Git
    records only for a directory with committed content. The file reached must
    be committed and unchanged. ``history`` returns the changes of the
    repository that contains a directory; a step in no repository, or in one
    where the revision is unknown, is not shown.

    With ``spelled``, ``parts`` are a path the caller wrote. A link among them
    that is kept outside every repository only says where things are, like the
    working directory, and is followed without proof. Link text never gets
    that allowance.
    """
    def recorded(path: Path, kind: str) -> bool:
        try:
            changes = history(path.parent if kind == 'blob' else path)
        except ChangeDetectionError:
            return False
        # Canonical spelling for Git; the parent holds no link at this point.
        path = Path(os.path.realpath(path.parent)) / path.name
        return _key(path) not in changes.files and path.is_relative_to(changes.root) and _in_history(changes, path, kind)

    pending = [(part, spelled) for part in reversed(parts)]
    entered: list[Path] = []  # Directories stepped into, which a later ".." would leave.
    current = start
    hops = 0
    while pending:
        part, written = pending.pop()
        if part == '..':
            if entered and not recorded(entered.pop(), 'tree'):
                return False
            current = current.parent
            continue
        candidate = current / part
        if candidate.is_symlink():
            hops += 1
            if hops > _MAX_LINK_HOPS:
                return False
            if not recorded(candidate, 'blob'):
                try:
                    history(current)
                except ChangeDetectionError:
                    if not written:
                        return False
                else:
                    return False
            try:
                text = Path(os.readlink(candidate))
            except OSError:
                return False
            if text.is_absolute():
                current, entered = Path(text.anchor), []
            pending.extend((name, False) for name in reversed(text.parts[1:] if text.is_absolute() else text.parts))
        elif pending:
            if not candidate.is_dir():
                return False
            entered.append(candidate)
            current = candidate
        else:
            return candidate.is_file() and recorded(candidate, 'blob')
    return False


def _applies_differently(changes: _Changes, path: Path, present: bool, history: Callable[[Path], _Changes]) -> bool:
    """Whether the configuration file ``path`` cannot be shown to apply to its
    directory exactly as it did at the baseline."""
    if path.is_symlink():
        return not _resolves_unchanged(path.parent, (path.name,), history, False)
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


def _changed_config(directory: Path, changes: _Changes, cache: dict[Path, Path | None],
                    history: Callable[[Path], _Changes]) -> Path | None:
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
                       if _applies_differently(changes, path, path in present, history)), None)
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
    repository that contains it, every skill is returned. Configuration reached
    through a symbolic link counts as unchanged only when the link and its
    target can both be compared with ``revision``; otherwise the skills it
    applies to are returned. ``notify`` receives one message per reason that
    widened the selection.

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

    def history(directory: Path) -> _Changes:
        root = _repository_root(directory, roots)
        if root not in changes:
            changes[root] = _changes(root, revision)
        return changes[root]

    everything = explicit_config is not None and _explicit_config_changed(explicit_config, revision, history, notify)
    selected = []
    for path in paths:
        directory = path.resolve().parent
        found = history(directory)
        root = found.root
        if everything or _key(directory) in found.directories:
            selected.append(path)
            continue
        if explicit_config is not None:
            continue
        config = _changed_config(directory, found, configs, history)
        if config is None:
            continue
        selected.append(path)
        if config not in notified:
            notified.add(config)
            state = ('changed since' if _key(config) in found.files
                     else _LINK_UNPROVEN if config.is_symlink() else 'has no history at')
            notify(f'Configuration {config.relative_to(root).as_posix()} {state} {revision}; validating the skills it applies to.')
    return selected


def _explicit_config_changed(config: Path, revision: str, history: Callable[[Path], _Changes],
                             notify: Callable[[str], None]) -> bool:
    """Compare a ``--config`` file with ``revision`` in its own repository.
    A file with no committed baseline there cannot be shown unchanged. One
    reached through a symbolic link or a ".." step is shown unchanged only by
    ``_resolves_unchanged``."""
    spelled = config.absolute()  # Not normalized: ".." after a link must not be collapsed lexically.
    try:
        resolved = config.resolve()
    except (OSError, RuntimeError):  # A link cycle, reported differently across Python versions.
        resolved = None
    if resolved != spelled:
        if resolved is not None and _resolves_unchanged(Path(spelled.anchor), spelled.parts[1:], history, True):
            return False
        notify(f'Configuration {config.name} {_LINK_UNPROVEN} {revision}; validating every skill.')
        return True
    try:
        found = history(resolved.parent)
        if _key(resolved) in found.files:
            notify(f'Configuration {config.name} changed since {revision}; validating every skill.')
            return True
        _git(found.root, 'cat-file', '-e', f'{found.commit}:{resolved.relative_to(found.root).as_posix()}')
        return False
    except ChangeDetectionError:
        notify(f'Configuration {config.name} has no history at {revision}; validating every skill.')
        return True
