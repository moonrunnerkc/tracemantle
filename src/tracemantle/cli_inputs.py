"""Input resolution for the validation CLI: discovering SKILL.md paths,
reading agent responses, and parsing a batch under its shared byte budget.

These functions exit with status 2 on input errors, as the CLI documents.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

from tracemantle import __version__
from tracemantle.agents._ingest import MAX_INGEST_BYTES
from tracemantle.config_loader import ConfigError, project_configs
from tracemantle.display import terminal
from tracemantle.git_changes import ChangeDetectionError, changed_skills
from tracemantle.io_limits import (
    MAX_SCAN_BYTES,
    MAX_SCAN_FILES,
    UntrustedInputError,
    display_path,
    read_guarded_text,
    reject_control_characters,
)
from tracemantle.parser import DocumentSettings, ParsedSkill, ParseError
from tracemantle.parser import parse as _parse_skill


def collect_paths(target: Path) -> list[Path]:
    """Return a list of SKILL.md files to validate.

    For a directory, recursively finds all files named exactly 'SKILL.md'.
    For a file, returns it directly without name filtering.

    Uses ``os.walk(followlinks=False)`` so directory symlinks are not traversed:
    a symlink into another tree cannot pull in foreign files, and a symlink cycle
    cannot hang the scan. ``Path.rglob`` follows directory symlinks on some Python
    versions, which this avoids.
    """
    if not target.is_dir():
        return [target]
    found: list[Path] = []
    def walk_error(exc: OSError) -> None:
        raise UntrustedInputError(f"Cannot scan {target}: {exc}") from exc

    for dirpath, dirnames, filenames in os.walk(target, followlinks=False, onerror=walk_error):
        dirnames[:] = sorted(d for d in dirnames if d not in {'.git', '.venv', '__pycache__', '.tracemantle'})
        if len(found) >= MAX_SCAN_FILES:
            raise UntrustedInputError(f"Scan exceeds the {MAX_SCAN_FILES}-file limit; split the batch.")
        if "SKILL.md" in filenames:
            found.append(Path(dirpath) / "SKILL.md")
    return sorted(found)


def resolve_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve the target paths to a list of SKILL.md files, exiting on error."""
    all_paths: list[Path] = []
    for target in args.path:
        if not target.exists():
            print(terminal(f"Error: path not found: {target}"), file=sys.stderr)
            sys.exit(2)
        try:
            paths = collect_paths(target)
        except (OSError, RuntimeError, UntrustedInputError) as exc:
            print(terminal(f"Error: {exc}"), file=sys.stderr)
            sys.exit(2)
        if not paths:
            print(terminal(f"No SKILL.md files found under: {target}"), file=sys.stderr)
            sys.exit(2)
        all_paths.extend(paths)
    try:
        unique = {p.resolve(): p for p in sorted(all_paths)}
        paths = [unique[key] for key in sorted(unique)]
        if len(paths) > MAX_SCAN_FILES:
            raise UntrustedInputError(f"Scan exceeds the {MAX_SCAN_FILES}-file limit.")
        discovered: dict[Path, tuple[Path, ...]] = {}
        if not args.config and any(project_configs(p, cache=discovered) != args.config_paths for p in paths):
            raise UntrustedInputError("Mixed project roots are ambiguous. Validate each project separately or supply --config.")
        if args.changed_since is not None:
            paths = changed_skills(paths, args.changed_since)
            if not paths:
                print(terminal(f"No skills changed since {args.changed_since}."), file=sys.stderr)
        return paths
    except ConfigError as exc:
        # Same contract as an invocation-level config failure in cli._apply_config.
        if args.format == 'json':
            print(json.dumps({'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2,
                              'gate': {'passed': False, 'exit_code': 2}, 'results': [], 'errors': [{'error': str(exc)}]}))
        else:
            print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(2)
    except (ChangeDetectionError, OSError, RuntimeError, UntrustedInputError) as exc:
        print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(2)


def read_ingest_raw(ingest_path: str, what: str) -> str:
    """Read a raw agent response from PATH or stdin, exiting on error.

    ``what`` names the response kind in errors, e.g. ``"critique response"``.

    Rejects payloads over ``MAX_INGEST_BYTES`` (exit 2). The stdin read is
    bounded so a runaway pipe cannot exhaust memory before the check fires.
    """
    if ingest_path == "-":
        payload = sys.stdin.buffer.read(MAX_INGEST_BYTES + 1)
        # Size first: truncation at the cap can split a code point, which would
        # otherwise be misreported as non-UTF-8 input.
        if len(payload) > MAX_INGEST_BYTES:
            print(
                f"Error: ingest payload from stdin exceeds the {MAX_INGEST_BYTES}-byte cap. "
                f"Trim the response or split the run into smaller batches.",
                file=sys.stderr,
            )
            sys.exit(2)
        try:
            raw = payload.decode('utf-8')
        except UnicodeDecodeError:
            print('Error: ingest stdin must contain UTF-8 text.', file=sys.stderr)
            sys.exit(2)
        # stdin arrives already decoded, so only the control-character half of
        # the policy applies. A pipe carrying NULs is a binary stream, not JSON.
        try:
            reject_control_characters(raw, what="Ingest payload", source="stdin")
        except UntrustedInputError as exc:
            print(terminal(f"Error: {exc}"), file=sys.stderr)
            sys.exit(2)
        return raw
    p = Path(ingest_path)
    if not p.exists():
        # Echoed verbatim, not through display_path. This is the string the user
        # typed on the command line, so shortening it hides which path they got
        # wrong. display_path exists to keep discovered content from publishing
        # the host layout, which does not apply to the user's own argument.
        print(terminal(f"Error: {what} file not found: {p}"), file=sys.stderr)
        sys.exit(2)
    try:
        return read_guarded_text(p, max_bytes=MAX_INGEST_BYTES, what="Ingest response")
    except UntrustedInputError as exc:
        print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(terminal(f"Error: cannot read {display_path(p)}: {exc}"), file=sys.stderr)
        sys.exit(2)


def parse_batch(paths: list[Path], settings: DocumentSettings | None = None) -> Iterator[tuple[Path, ParsedSkill | ParseError]]:
    """Parse each path in order under the shared batch byte budget.

    Every mode reads through here, so a batch is capped at ``MAX_SCAN_BYTES``
    of source in total, not only per file. A file that cannot be parsed, or
    that would exceed the remaining budget, yields its ``ParseError`` so the
    caller can report it and continue with independent files.
    """
    scanned = 0
    for path in paths:
        try:
            if scanned >= MAX_SCAN_BYTES:
                raise ParseError(f"Scan exceeds the {MAX_SCAN_BYTES}-byte budget. Split the batch.")
            skill = _parse_skill(path, settings=settings, max_bytes=MAX_SCAN_BYTES - scanned)
        except ParseError as exc:
            yield path, exc
            continue
        scanned += len(skill.raw_bytes)
        yield path, skill
