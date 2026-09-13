"""A bounded Markdown resource tokenizer shared by analysis and manifests.

This deliberately supports a documented subset, not HTML or Markdown execution.
Unsupported dynamic references remain unknown dependencies in bundle reports.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|(?:[^\s()\\]|\\.|\([^()\n]*\))+)\s*(?:[\"\x27][^\n]*?[\"\x27]\s*)?\)')
_DEFINITION = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)')
_REFERENCE = re.compile(r'\[([^\]\n]+)\](?:\[([^\]\n]*)\])?')
_HTML = re.compile(r'<(?:a|img)\s+[^>]*?(?:href|src)\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]', re.I)
_CODE_BOUNDARY = re.compile(r'`+|\n[ \t]*\n')
_RESOURCE_PATH = re.compile(r'[^\s`]+/[^\s`]+')
_DIRECTIVE = re.compile(r'(?:source|file|include):\s*([^\s]+\.[a-zA-Z0-9]+)', re.I)
_LIST = re.compile(r'^ {0,3}([-+*]|[0-9]{1,9}[.)])( +|$)')
_PREFIX = re.compile(r'^[ \t]*(?:(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)?')
_BLOCK_END = re.compile(r'^(?:#{1,6}\s|[-*_]{3,}\s*$)')


@dataclass(frozen=True, slots=True)
class Resource:
    target: str
    line: int
    kind: str


@dataclass(frozen=True, slots=True)
class Markdown:
    visible_lines: tuple[str, ...]
    resources: tuple[Resource, ...]
    headings: tuple[tuple[int, int, str], ...]
    uncertain: bool = False


def _inline_code(lines: list[str], blocks: list[int]) -> tuple[list[str], dict[int, list[str]]]:
    """Mask exact-delimiter code spans in linear passes, retaining path mentions."""
    text = '\n'.join(lines)
    if '`' not in text:
        return lines, {}
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    boundaries = [starts[number] for number in blocks]
    runs = list(_CODE_BOUNDARY.finditer(text))
    next_run: dict[int, int] = {}
    pairs: dict[int, int] = {}
    escaped: set[int] = set()
    for index in range(len(runs) - 1, -1, -1):
        while boundaries and runs[index].start() < boundaries[-1]:
            next_run.clear()
            boundaries.pop()
        if runs[index][0].startswith('\n'):
            next_run.clear()
            continue
        length = runs[index].end() - runs[index].start()
        offset = runs[index].start() - 1
        while offset >= 0 and text[offset] == '\\':
            offset -= 1
        odd = (runs[index].start() - 1 - offset) % 2
        if odd:
            escaped.add(index)
        # Outside a span an escape consumes the first backtick only. Inside
        # a span backslashes are literal, so closers retain their full length.
        if length - odd in next_run:
            pairs[index] = next_run[length - odd]
        next_run[length] = index
    masked = list(text)
    paths: dict[int, list[str]] = {}
    index = 0
    while index < len(runs):
        end = pairs.get(index)
        if end is None:
            index += 1
            continue
        opener, closer = runs[index], runs[end]
        target = text[opener.end():closer.start()].strip()
        path_like = _RESOURCE_PATH.fullmatch(target) and not any(
            pattern.fullmatch(target) for pattern in (_LINK, _REFERENCE, _DIRECTIVE)
        )
        if path_like or re.fullmatch(r'[\w.-]+\.[a-zA-Z0-9]+', target):
            line_number = bisect_right(starts, opener.start()) - 1
            paths.setdefault(line_number, []).append(target)
        for offset in range(opener.start() + (index in escaped), closer.end()):
            if masked[offset] != '\n':
                masked[offset] = ' '
        index = end + 1
    return ''.join(masked).split('\n'), paths


def _blocks(body: str) -> tuple[list[str], list[str], list[int], bool]:
    """Recognize ordinary lists/continuations; refuse complete container guesses."""
    visible: list[str] = []
    content: list[str] = []
    indents: list[int] = []
    blocks: list[int] = []
    paragraph = False
    uncertain = False
    fence = ''
    fence_indent = 0
    for original in body.splitlines():
        if not original.strip():
            visible.append('')
            content.append('')
            paragraph = False
            continue
        line = original
        if '\t' in original:
            prefix = _PREFIX.match(original)
            assert prefix is not None
            line = prefix[0].expandtabs(4) + original[prefix.end():]
        indent = len(line) - len(line.lstrip(' '))
        if fence and indent < fence_indent:
            fence = ''  # Leaving the list container also ends its code block.
        if fence:
            match = _FENCE.match(line[fence_indent:])
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = ''
            visible.append('')
            content.append('')
            continue
        if indents and indent < indents[-1] and paragraph and not (
            _LIST.match(line) or _FENCE.match(line) or _BLOCK_END.match(line)
        ):
            uncertain = True  # Lazy outdented continuation needs a full block parser.
        while indents and indent < indents[-1]:
            indents.pop()
        base = indents[-1] if indents else 0
        if indent - base >= 4 and not paragraph:
            visible.append('')
            content.append('')
            continue
        normalized = line[base:]
        marker = _LIST.match(normalized)
        if not paragraph or marker or _BLOCK_END.match(normalized):
            blocks.append(len(content))
        if marker:
            padding = len(marker[2])
            width = marker.end() if padding <= 4 else marker.end() - padding + 1
            if not normalized[marker.end():].strip():
                width = marker.start(2) + 1
            if len(indents) < 32:
                indents.append(base + width)
            else:
                uncertain = True
            base += width
            normalized = line[base:]
            paragraph = False
            # Same-line nested containers are outside the supported subset.
            if _LIST.match(normalized):
                uncertain = True
            if padding > 4:
                visible.append('')
                content.append('')
                continue
        match = _FENCE.match(normalized)
        if match and not (match[1][0] == '`' and '`' in match[2]):
            fence = match[1]
            fence_indent = base
            paragraph = False
            visible.append('')
            content.append('')
        else:
            if normalized.lstrip().startswith('>'):
                uncertain = True  # Blockquote/container nesting is not parsed.
            visible.append(original)
            content.append(normalized.lstrip(' '))
            paragraph = bool(normalized.strip()) and not bool(_BLOCK_END.match(normalized))
    return visible, content, blocks, uncertain


def tokenize(body: str, start_line: int = 1) -> Markdown:
    visible, content, blocks, uncertain = _blocks(body)
    extraction, inline_paths = _inline_code(content, blocks)
    definitions = {m[1].casefold(): m[2] for line in extraction if (m := _DEFINITION.match(line))}
    resources: list[Resource] = []
    headings: list[tuple[int, int, str]] = []
    seen: set[tuple[str, str]] = set()
    for number, line in enumerate(extraction, start_line):
        heading = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading:
            headings.append((number, len(heading[1]), content[number - start_line][heading.start(2):]))
        candidates = [(m[1], 'link') for m in _LINK.finditer(line)]
        candidates.extend((m[1], 'link') for m in _HTML.finditer(line))
        candidates.extend((m[1], 'resource') for m in _DIRECTIVE.finditer(line))
        for m in _REFERENCE.finditer(line):
            label = (m[2] or m[1]).casefold()
            if label in definitions:
                candidates.append((definitions[label], 'link'))
        for target in inline_paths.get(number - start_line, []):
            candidates.append((target, 'resource' if '/' in target else 'generated'))
        for raw, kind in candidates:
            target = unquote(re.sub(r'\\([() ])', r'\1', raw.strip('<>')))
            if any(c in target for c in '<>${}'):
                uncertain = True
                continue
            try:
                parsed = urlsplit(target)
            except ValueError:
                uncertain = True
                continue
            if parsed.scheme or parsed.netloc:
                kind = 'external'
            elif not parsed.path:
                kind = 'anchor'
            else:
                target = parsed.path
            if (target, kind) not in seen:
                resources.append(Resource(target, number, kind))
                seen.add((target, kind))
    return Markdown(tuple(visible), tuple(resources), tuple(headings), uncertain)
