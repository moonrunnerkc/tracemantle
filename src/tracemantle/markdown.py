"""A bounded Markdown resource tokenizer shared by analysis and manifests.

This deliberately supports a documented subset, not HTML or Markdown execution.
Unsupported dynamic references remain unknown dependencies in bundle reports.
"""
from __future__ import annotations

import html
import re
from bisect import bisect_right
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
# Labels, titles and HTML attributes exclude their own opening delimiter so each
# candidate scan stops at the next one; untrusted lines stay linear to match.
_LINK = re.compile(r'!?\[[^\[\]\n]*\]\(\s*(<[^>\n]+>|(?:[^\s()\\]|\\.|\([^()\n]*\))+)(?:\s+(?:"[^"\n]*"|\x27[^\x27\n]*\x27))?\s*\)')
_DEFINITION = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)')
_REFERENCE = re.compile(r'\[([^\[\]\n]+)\](?:\[([^\[\]\n]*)\])?')
_HTML = re.compile(r'<(?:a|img)\s+[^<>]*?(?:href|src)\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]', re.I)
_CODE_BOUNDARY = re.compile(r'`+|\n[ \t]*\n')
_DIRECTIVE = re.compile(r'(?<![\w:/.-])(?:source|file|include):\s*([^\s]+\.[a-zA-Z0-9]+)', re.I)
_LIST = re.compile(r'^ {0,3}([-+*]|[0-9]{1,9}[.)])( +|$)')
_PREFIX = re.compile(r'^[ \t]*(?:(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)?')
_BLOCK_END = re.compile(r'^ {0,3}(?:#{1,6}(?:[ \t]|$)|(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$|(?:-[ \t]*){3,}$)')
_SETEXT = re.compile(r'^ {0,3}(?:=+|-+)[ \t]*$')
_BRACKET = re.compile(r'[\\\[\]]')
_ESCAPABLE = frozenset('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
# Backslash escapes and entity references are literal text once decoded, so one
# pass handles both. The escaped space is a retained pre-CommonMark extension.
_ESCAPE_OR_ENTITY = re.compile(r'\\([!-/:-@\[-`{-~ ])|&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});')
_DEFINITION_LIKE = re.compile(r'\[(?:[^\[\]\\\n]|\\.){1,999}\]:')
_MAX_LABEL = 999  # CommonMark 0.31.2 link label limit.
_MAX_PARENS = 32  # Same nesting bound as the reference implementation; keeps failed scans short.


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
        # An interior separator in one whitespace-free token, tested without
        # a backtracking pattern over the untrusted span.
        path_like = re.fullmatch(r'[^\s`]+', target) and '/' in target[1:-1] and not any(
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
        if paragraph and _SETEXT.fullmatch(normalized):
            # The underline ends the entire preceding paragraph as a heading.
            # Resolve this before list markers and inline spans, without
            # splitting the heading's potentially multiline inline content.
            blocks.append(len(content))
            visible.append(original)
            content.append('')
            paragraph = False
            continue
        block_end = bool(_BLOCK_END.match(normalized))
        marker = _LIST.match(normalized)
        if block_end:
            marker = None  # A thematic break takes precedence over a list item.
        if not paragraph or marker or block_end:
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


def _skip_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset] in ' \t\n':
        offset += 1
    return offset


def _escaped(text: str, offset: int) -> bool:
    return text[offset] == '\\' and offset + 1 < len(text) and text[offset + 1] in _ESCAPABLE


def _destination(text: str, offset: int) -> tuple[str, int] | None:
    """Return a raw link destination and the offset after it."""
    if offset >= len(text):
        return None
    end = offset
    if text[offset] == '<':
        end += 1
        while end < len(text) and text[end] not in '<\n':
            if text[end] == '>':
                return text[offset + 1:end], end + 1
            end += 2 if _escaped(text, end) else 1
        return None
    depth = 0
    while end < len(text) and not text[end].isspace():
        if text[end] == '\\' and end + 1 < len(text) and (text[end + 1] in _ESCAPABLE or text[end + 1] == ' '):
            end += 2
            continue
        if text[end] == '(':
            depth += 1
            if depth > _MAX_PARENS:
                return None
        elif text[end] == ')':
            if not depth:
                break
            depth -= 1
        end += 1
    return None if depth or end == offset else (text[offset:end], end)


def _title_end(text: str, offset: int, unclosed: set[str]) -> int | None:
    """Return the offset after a title. ``unclosed`` remembers quote characters
    with no closer in the rest of the block, so repeated openers stay linear."""
    opener = text[offset]
    if opener in unclosed:
        return None
    closer = ')' if opener == '(' else opener
    end = offset + 1
    while end < len(text):
        if _escaped(text, end):
            end += 2
            continue
        if text[end] == closer:
            return end + 1
        if opener == '(' and text[end] == '(':
            return None
        end += 1
    if opener != '(':
        unclosed.add(opener)
    return None


def _label(raw: str) -> str:
    return ' '.join(raw.split()).casefold()


@dataclass(slots=True)
class _Links:
    """Inline destinations and reference-label uses by line index, plus the
    first definition of each normalized label. ``interrupting`` holds
    definition-shaped lines inside a paragraph: CommonMark renders them as
    text, so they never take precedence over a real definition."""
    inline: dict[int, list[str]] = field(default_factory=dict)
    uses: dict[int, list[str]] = field(default_factory=dict)
    definitions: dict[str, str] = field(default_factory=dict)
    interrupting: dict[str, str] = field(default_factory=dict)
    uncertain: bool = False


def _definition_end(text: str, offset: int, first_line: int, starts: list[int], links: _Links,
                    unclosed: set[str], *, interrupting: bool = False) -> int | None:
    """Consume one link reference definition at a line start; None if absent."""
    match = _DEFINITION_LIKE.match(text, offset)
    if match is None:
        # A label may also span lines, which the single-line guard cannot see.
        close = text.find(']', offset)
        if not text.startswith('[', offset) or close < 0 or close - offset - 1 > _MAX_LABEL or not text.startswith(':', close + 1):
            return None
        raw = text[offset + 1:close]
        if '[' in raw or '\\' in raw:
            return None
    else:
        raw = text[offset + 1:match.end() - 2]
    if not raw.strip():
        return None
    after_label = offset + len(raw) + 3
    found = _destination(text, _skip_space(text, after_label))
    if found is None:
        return None
    destination, end = found
    line_end = end
    while line_end < len(text) and text[line_end] in ' \t':
        line_end += 1
    if line_end < len(text) and text[line_end] != '\n':
        # A same-line title needs separating whitespace and nothing after it.
        title = _title_end(text, line_end, unclosed) if line_end > end and text[line_end] in '"\'(' else None
        if title is None:
            return None
        line_end = title
        while line_end < len(text) and text[line_end] in ' \t':
            line_end += 1
        if line_end < len(text) and text[line_end] != '\n':
            return None
    else:
        # A title on the following line is optional: if it does not parse, the
        # definition ends here and that line is ordinary paragraph text.
        title_start = _skip_space(text, line_end)
        if title_start < len(text) and text[title_start] in '"\'(':
            title = _title_end(text, title_start, unclosed)
            if title is not None:
                while title < len(text) and text[title] in ' \t':
                    title += 1
                if title == len(text) or text[title] == '\n':
                    line_end = title
    label = _label(raw)
    line = first_line + bisect_right(starts, offset) - 1
    if interrupting:
        # Other renderers accept this as a definition, so its destination stays
        # governed, but it must not shadow the definition CommonMark would use.
        links.interrupting.setdefault(label, destination)
        links.inline.setdefault(line, []).append(destination)
    else:
        links.definitions.setdefault(label, destination)
        # A definition also counts as a use of its label, so a defined helper
        # is governed even when no link in the document refers to it.
        links.uses.setdefault(line, []).append(label)
    return min(line_end + 1, len(text))


def _scan_block(text: str, first_line: int, links: _Links) -> None:
    """Collect links from one paragraph-level block in a single forward pass.

    Every bracket pair that could be a link label is recorded as a use, so
    full, collapsed and shortcut references all resolve without lookahead. This
    is deliberately a superset of CommonMark's link set: an extra governed
    helper is safe, a missed one permits stale evidence reuse.
    """
    starts = [0]
    starts.extend(m.end() for m in re.finditer('\n', text))
    unclosed: set[str] = set()
    offset = 0
    while offset < len(text):
        end = _definition_end(text, offset, first_line, starts, links, unclosed)
        if end is None:
            break
        offset = end
    for start in starts[bisect_right(starts, offset) - 1:]:
        if start >= offset and _DEFINITION_LIKE.match(text, start) and _definition_end(
                text, start, first_line, starts, links, unclosed, interrupting=True) is None:
            links.uncertain = True  # Shaped like a definition, with a destination that does not parse.
    openers: list[tuple[int, bool]] = []
    while (match := _BRACKET.search(text, offset)) is not None:
        offset = match.start()
        if text[offset] == '\\':
            offset += 2 if _escaped(text, offset) else 1
            continue
        if text[offset] == '[':
            openers.append((offset, False))
            offset += 1
            continue
        offset += 1
        if not openers:
            continue
        opened, nested = openers.pop()
        if openers:
            openers[-1] = (openers[-1][0], True)
        if text.startswith('(', offset):
            start = _skip_space(text, offset + 1)
            found = ('', start) if text.startswith(')', start) else _destination(text, start)
            if found is not None:
                destination, end = found
                after = _skip_space(text, end)
                if after > end and after < len(text) and text[after] in '"\'(':
                    title = _title_end(text, after, unclosed)
                    after = len(text) if title is None else _skip_space(text, title)
                if text.startswith(')', after):
                    if destination:
                        links.inline.setdefault(first_line + bisect_right(starts, start) - 1, []).append(destination)
                    offset = after + 1
                    continue
            links.uncertain = True  # Bracketed text with a destination that does not parse.
        raw = text[opened + 1:offset - 1]
        if not nested and len(raw) <= _MAX_LABEL and raw.strip():
            links.uses.setdefault(first_line + bisect_right(starts, opened) - 1, []).append(_label(raw))


def _links(lines: list[str], blocks: list[int]) -> _Links:
    links = _Links()
    boundaries = set(blocks)
    first = 0
    for index in range(len(lines) + 1):
        if index < len(lines) and lines[index] and (index == first or index not in boundaries):
            continue
        if index > first:
            _scan_block('\n'.join(lines[first:index]), first, links)
        first = index if index < len(lines) and lines[index] else index + 1
    return links


def _decode(raw: str) -> str:
    return unquote(_ESCAPE_OR_ENTITY.sub(lambda m: m[1] or html.unescape(m[0]), raw))


def _plain(raw: str) -> str:
    """HTML attributes, directives and code-span paths are not Markdown link
    destinations; they keep their narrower historical unescaping."""
    return unquote(re.sub(r'\\([() ])', r'\1', raw.strip('<>')))


def tokenize(body: str, start_line: int = 1) -> Markdown:
    visible, content, blocks, uncertain = _blocks(body)
    extraction, inline_paths = _inline_code(content, blocks)
    links = _links(extraction, blocks)
    uncertain |= links.uncertain
    definitions = links.interrupting | links.definitions
    resources: list[Resource] = []
    headings: list[tuple[int, int, str]] = []
    seen: set[tuple[str, str]] = set()
    for number, line in enumerate(extraction, start_line):
        heading = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading:
            headings.append((number, len(heading[1]), content[number - start_line][heading.start(2):]))
        index = number - start_line
        candidates = [(_decode(raw), 'link') for raw in links.inline.get(index, [])]
        candidates.extend((_plain(m[1]), 'link') for m in _HTML.finditer(line))
        candidates.extend((_plain(m[1]), 'resource') for m in _DIRECTIVE.finditer(line))
        candidates.extend((_decode(definitions[label]), 'link') for label in links.uses.get(index, []) if definitions.get(label))
        for target in inline_paths.get(index, []):
            candidates.append((_plain(target), 'mention' if '/' in target else 'generated'))
        for target, kind in candidates:
            template_path = target.removeprefix('{baseDir}/')
            if any(c in template_path for c in '<>${}'):
                uncertain = True
                continue
            if any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in target):
                # urlsplit strips leading controls; retain the original decoded
                # reference so boundary validation can reject it explicitly.
                uncertain = True
                if (target, kind) not in seen:
                    resources.append(Resource(target, number, kind))
                    seen.add((target, kind))
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
