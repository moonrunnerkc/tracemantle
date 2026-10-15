"""Bounded resource closure; paths and chain lengths have different meanings."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tracemantle.io_limits import MAX_SCAN_BYTES, MAX_SCAN_FILES, MAX_SKILL_BYTES, UntrustedInputError, read_bounded_bytes
from tracemantle.markdown import Markdown, tokenize
from tracemantle.result import Diagnostic, Severity


@dataclass(frozen=True, slots=True)
class Dependencies:
    paths: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    diagnostics: tuple[Diagnostic, ...]
    complete: bool


def analyze_dependencies(path: Path, markdown: Markdown, *,
                         reference_format: Literal['relative', 'skill-base-dir'] = 'relative') -> Dependencies:
    if reference_format not in {'relative', 'skill-base-dir'}:
        raise ValueError('Unknown resource reference format.')
    root = path.parent.resolve()
    paths: set[str] = set()
    edges: set[tuple[str, str]] = set()
    asserted_edges: set[tuple[str, str]] = set()
    diagnostics: list[Diagnostic] = []
    complete = not markdown.uncertain
    scanned = 0
    expanded: set[Path] = set()
    pending: list[tuple[Path, Markdown, tuple[Path, ...], int]] = [(path.resolve(), markdown, (path.resolve(),), 0)]
    while pending:
        source, document, ancestors, origin_line = pending.pop()
        complete &= not document.uncertain
        for ref in document.resources:
            if ref.kind in {'external', 'anchor', 'generated'}:
                continue
            line = origin_line or ref.line
            if ref.kind == 'mention':
                diagnostics.append(Diagnostic('references.uncertain', Severity.WARNING,
                    f"Inline path '{ref.target}' may be a resource, example or runtime input; dependency coverage is incomplete. Use an explicit link for a required resource.", line=line))
                complete = False
            if any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in ref.target):
                diagnostics.append(Diagnostic('references.unreadable', Severity.ERROR,
                    'Reference contains a decoded control character.', line=line))
                complete = False
                continue
            target_text = ref.target
            base = source.parent
            if target_text.startswith('{baseDir}/'):
                if reference_format != 'skill-base-dir':
                    diagnostics.append(Diagnostic('references.uncertain', Severity.WARNING,
                        f"Reference '{ref.target}' needs an explicit skill-base-dir interpretation.", line=line))
                    complete = False
                    continue
                base = root
                target_text = target_text[len('{baseDir}/'):]
                # A rooted suffix or Windows separator must not reinterpret the
                # selected root differently on another host.
                if target_text.startswith('/') or '\\' in target_text or ':' in target_text:
                    if ref.kind != 'mention':
                        diagnostics.append(Diagnostic('references.escape', Severity.ERROR,
                            f"Reference '{ref.target}' has an unsafe skill-root path.", line=line))
                    complete = False
                    continue
            try:
                # Expand a leading ~ to the user's home directory before
                # resolving. Without this, a reference like `~/notes/tips.md`
                # is joined onto the skill directory as a literal "~"
                # segment and misreported as a broken link.
                relative_path = Path(target_text)
                if not ref.target.startswith('{baseDir}/'):
                    relative_path = relative_path.expanduser()
                target = (base / relative_path).resolve()
                if not target.is_relative_to(root):
                    if ref.kind != 'mention':
                        diagnostics.append(Diagnostic('references.escape', Severity.ERROR, f"Reference '{ref.target}' resolves outside the skill directory.", line=line))
                    complete = False
                    continue
                relative = target.relative_to(root).as_posix()
                paths.add(relative)
                if len(paths) > MAX_SCAN_FILES:
                    diagnostics.append(Diagnostic('references.unreadable', Severity.ERROR, 'Reference path count exceeds its limit; split the bundle.', line=line))
                    return Dependencies(tuple(sorted(paths)), tuple(sorted(edges)), tuple(diagnostics), False)
                edges.add((source.relative_to(root).as_posix(), relative))
                if ref.kind == 'mention':
                    continue  # Retain a possible edge without asserting its existence or contents.
                asserted_edges.add((source.relative_to(root).as_posix(), relative))
                if target in ancestors:
                    diagnostics.append(Diagnostic('references.cycle', Severity.ERROR, f"Reference cycle through '{relative}'. Break the cycle.", line=line))
                    complete = False
                    continue
                if not target.exists():
                    diagnostics.append(Diagnostic('references.broken-link', Severity.ERROR, f"Referenced file does not exist: '{ref.target}'.", line=line, context=f'resolved to: {relative}'))
                    complete = False
                    continue
                if len(ancestors) > 1:
                    diagnostics.append(Diagnostic('references.depth-exceeded', Severity.WARNING, f"Reference '{relative}' has chain depth {len(ancestors)} from SKILL.md (recommended maximum 1).", line=line))
                if target in expanded or target.suffix.lower() not in {'.md', '.markdown'} or not target.is_file():
                    continue
                if len(ancestors) >= 32 or len(expanded) >= MAX_SCAN_FILES:
                    raise UntrustedInputError('Reference traversal exceeds its depth/file limit; simplify dependencies.')
                raw = read_bounded_bytes(target, max_bytes=min(MAX_SKILL_BYTES, MAX_SCAN_BYTES - scanned), what='Reference')
                scanned += len(raw)
                expanded.add(target)
                pending.append((target, tokenize(raw.decode('utf-8-sig')), (*ancestors, target), line))
            except (OSError, RuntimeError, UnicodeError, UntrustedInputError) as exc:
                if ref.kind != 'mention':
                    diagnostics.append(Diagnostic('references.unreadable', Severity.ERROR, f"Cannot inspect reference '{ref.target}': {exc}", line=line))
                complete = False
    # Shared children may be expanded before their parents; check the completed
    # edge set so traversal order cannot conceal a cross-branch cycle.
    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for source_name, target_name in sorted(asserted_edges):
        outgoing[source_name].append(target_name)
        incoming[target_name] += 1
        incoming.setdefault(source_name, 0)
    ready = deque(sorted(name for name, count in incoming.items() if count == 0))
    while ready:
        source_name = ready.popleft()
        for target_name in outgoing[source_name]:
            incoming[target_name] -= 1
            if incoming[target_name] == 0:
                ready.append(target_name)
    cyclic = sorted(name for name, count in incoming.items() if count)
    if cyclic:
        complete = False
        if not any(d.rule == 'references.cycle' for d in diagnostics):
            diagnostics.append(Diagnostic('references.cycle', Severity.ERROR, f'Reference cycle in resource closure through {cyclic[0]!r}. Break the cycle.', line=markdown.resources[0].line if markdown.resources else 1))
    unique = {(d.rule, d.line, d.message): d for d in diagnostics}
    return Dependencies(tuple(sorted(paths)), tuple(sorted(edges)), tuple(unique[k] for k in sorted(unique, key=str)), complete)
