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
# _LINK and _REFERENCE only recognize a code span whose whole content is link
# syntax, so it is not mistaken for a path. Links themselves are found by
# _scan_block.
_LINK = re.compile(r'!?\[[^\[\]\n]*\]\(\s*(<[^>\n]+>|(?:[^\s()\\]|\\.|\([^()\n]*\))+)(?:\s+(?:"[^"\n]*"|\x27[^\x27\n]*\x27))?\s*\)')
_REFERENCE = re.compile(r'\[([^\[\]\n]+)\](?:\[([^\[\]\n]*)\])?')
_HTML = re.compile(r'<(?:a|img)\s[^<>]*?(?:href|src)\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]', re.I)
_CODE_BOUNDARY = re.compile(r'`+|\n[ \t]*\n')
# The whole whitespace-free run is consumed so a failed candidate is not
# rescanned from every later directive word inside it; _DIRECTIVE_PATH then
# keeps the longest prefix that ends in a file extension.
_DIRECTIVE = re.compile(r'(?<![\w:/.-])(?:source|file|include):\s*(\S+)', re.I)
_DIRECTIVE_PATH = re.compile(r'.*\.[a-zA-Z0-9]+', re.S)
_LIST = re.compile(r'^ {0,3}([-+*]|[0-9]{1,9}[.)])( +|$)')
_PREFIX = re.compile(r'^[ \t]*(?:(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)?')
_BLOCK_END = re.compile(r'^ {0,3}(?:#{1,6}(?:[ \t]|$)|(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$|(?:-[ \t]*){3,}$)')
_SETEXT = re.compile(r'^ {0,3}(?:=+|-+)[ \t]*$')
# CommonMark 0.31.2 section 4.6 HTML block start conditions, tested on a line
# with its container prefix removed. Kinds 1 to 5 end on a line containing the
# paired text and may span blank lines; kinds 6 and 7 end at a blank line.
_HTML_ENDS = (
    (re.compile(r' {0,3}<(?:pre|script|style|textarea)(?:[ \t>]|$)', re.I), re.compile(r'</(?:pre|script|style|textarea)>', re.I)),
    (re.compile(r' {0,3}<!--'), re.compile(r'-->')),
    (re.compile(r' {0,3}<\?'), re.compile(r'\?>')),
    (re.compile(r' {0,3}<![A-Za-z]'), re.compile(r'>')),
    (re.compile(r' {0,3}<!\[CDATA\['), re.compile(r'\]\]>')),
)
_HTML_BLOCK_TAG = re.compile(
    r' {0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt'
    r'|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav'
    r'|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:[ \t>]|/>|$)', re.I)
# Kind 7: one complete open or closing tag alone on its line. Each attribute
# starts with required whitespace and its parts cannot overlap, so a line that
# fails to match is rejected in linear time.
_HTML_LONE_TAG = re.compile(
    r' {0,3}(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t]*=[ \t]*(?:[^ \t"\x27=<>`]+|\x27[^\x27]*\x27|"[^"]*"))?)*[ \t]*/?>'
    r'|</[A-Za-z][A-Za-z0-9-]*[ \t]*>)[ \t]*$')
# CommonMark 0.31.2 starts a block at these names, and at a lowercase
# declaration, where 0.29, which GitHub Flavored Markdown follows, does not, or
# the reverse. Renderers then disagree about where the block ends, so the
# structure after it is not trusted.
_HTML_VERSION_DEPENDENT = re.compile(r' {0,3}(?:(?i:</?(?:textarea|search|source))(?:[ \t>]|/>|$)|<![a-z])')
_BRACKET = re.compile(r'[\\\[\]]')
_ESCAPABLE = frozenset('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
# Backslash escapes and entity references are literal text once decoded, so one
# pass handles both. The escaped space is a retained pre-CommonMark extension.
_ESCAPE_OR_ENTITY = re.compile(r'\\([!-/:-@\[-`{-~ ])|&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});')
# A code span cannot begin inside an HTML tag, comment or autolink, but the span
# masker does not parse those; a backtick there leaves later links unresolved.
_BACKTICK_IN_ANGLE = re.compile(r'<[A-Za-z!/?][^<>`\n]*`[^<>\n]*>')
# str.splitlines breaks on these; CommonMark does not, so block structure
# around them cannot be trusted.
_FOREIGN_LINE_BREAK = re.compile('[\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]')
_MAX_DEFINITIONS = 8  # Conflicting destinations kept per label before coverage is incomplete.
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
            pattern.fullmatch(target) for pattern in (_LINK, _REFERENCE)
        ) and not ((directive := _DIRECTIVE.fullmatch(target)) and _DIRECTIVE_PATH.fullmatch(directive[1]))
        if path_like or re.fullmatch(r'[\w.-]+\.[a-zA-Z0-9]+', target):
            line_number = bisect_right(starts, opener.start()) - 1
            paths.setdefault(line_number, []).append(target)
        for offset in range(opener.start() + (index in escaped), closer.end()):
            if masked[offset] != '\n':
                masked[offset] = ' '
        index = end + 1
    return ''.join(masked).split('\n'), paths


def _html_block_start(line: str, in_paragraph: bool) -> tuple[bool, re.Pattern[str] | None]:
    """Return whether ``line`` starts an HTML block, and the pattern that ends
    it. No pattern means the block ends at the next blank line."""
    if '<' not in line[:4]:
        return False, None
    for start, end in _HTML_ENDS:
        if start.match(line):
            return True, end
    # Only a lone tag cannot interrupt a paragraph.
    return bool(_HTML_BLOCK_TAG.match(line) or (not in_paragraph and _HTML_LONE_TAG.match(line))), None


def _html_line(line: str) -> str:
    """Return a raw HTML block line for extraction. Backticks are literal there,
    so they are removed before code spans are paired; href, src and link syntax
    stay readable and keep any helper they name governed."""
    return line.lstrip(' ').replace('`', ' ')


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
    in_html = False
    html_end: re.Pattern[str] | None = None  # None while in_html: the block ends at a blank line.
    html_indent = 0
    for original in body.splitlines():
        if not original.strip(' \t'):
            visible.append('')
            content.append('')
            paragraph = False
            in_html = in_html and html_end is not None
            # Renderers disagree on whether a blank line ends such a block
            # when it sits inside a list item.
            uncertain |= in_html and html_indent > 0
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
        if in_html and indent < html_indent:
            in_html = False  # As for a fence, the block ends with its list container.
        if in_html:
            visible.append(original)
            content.append(_html_line(line))
            in_html = html_end is None or html_end.search(line) is None
            continue
        if indents and indent < indents[-1] and paragraph and not (
            _LIST.match(line) or _FENCE.match(line) or _BLOCK_END.match(line)
        ):
            uncertain = True  # Lazy outdented continuation needs a full block parser.
        left_container = bool(indents) and indent < indents[-1]
        while indents and indent < indents[-1]:
            indents.pop()
        base = indents[-1] if indents else 0
        if indent - base >= 4 and not paragraph:
            visible.append('')
            content.append('')
            continue
        normalized = line[base:]
        # Outdented below a list item, a lone marker starts an empty item instead.
        if paragraph and _SETEXT.fullmatch(normalized) and not (left_container and _LIST.match(normalized)):
            # The underline ends the entire preceding paragraph as a heading.
            # Resolve this before list markers and inline spans, without
            # splitting the heading's potentially multiline inline content.
            # If definitions consume the whole paragraph, the line is text
            # instead and the paragraph continues; that needs the inline pass.
            # A line that is also a thematic break ends the block either way.
            uncertain |= bool(blocks) and _definition_label(content[blocks[-1]], 0) is not None and not _BLOCK_END.match(normalized)
            blocks.append(len(content))
            visible.append(original)
            content.append('')
            paragraph = False
            continue
        block_end = bool(_BLOCK_END.match(normalized))
        marker = _LIST.match(normalized)
        if block_end:
            marker = None  # A thematic break takes precedence over a list item.
        if marker and paragraph and not left_container and (
                not normalized[marker.end():].strip() or (marker[1][0].isdigit() and int(marker[1][:-1]) != 1)):
            # Only a non-empty item, numbered 1 if ordered, can start a new
            # list inside a paragraph; anything else is paragraph text.
            marker = None
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
        if _HTML_VERSION_DEPENDENT.match(normalized):
            uncertain = True
        starts_html, html_end = _html_block_start(normalized, paragraph)
        if starts_html:
            if paragraph:
                blocks.append(len(content))
            html_indent = base
            in_html = html_end is None or html_end.search(normalized) is None
            paragraph = False
            visible.append(original)
            content.append(_html_line(normalized))
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
            paragraph = bool(normalized.strip(' \t')) and not bool(_BLOCK_END.match(normalized))
    return visible, content, blocks, uncertain


def _skip_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset] in ' \t\n':
        offset += 1
    return offset


def _escaped(text: str, offset: int) -> bool:
    return text[offset] == '\\' and offset + 1 < len(text) and text[offset + 1] in _ESCAPABLE


def _destination(text: str, offset: int) -> tuple[str | None, int]:
    """Return a raw link destination and the offset after it, or None and the
    offset where the scan gave up."""
    end = offset
    if text.startswith('<', offset):
        end += 1
        while end < len(text) and text[end] not in '<\n':
            if text[end] == '>':
                return text[offset + 1:end], end + 1
            end += 2 if _escaped(text, end) else 1
        return None, end
    depth = 0
    while end < len(text) and not text[end].isspace():
        if text[end] == '\\' and end + 1 < len(text) and (text[end + 1] in _ESCAPABLE or text[end + 1] == ' '):
            end += 2
            continue
        if text[end] == '(':
            depth += 1
            if depth > _MAX_PARENS:
                return None, end
        elif text[end] == ')':
            if not depth:
                break
            depth -= 1
        end += 1
    return (None, end) if depth or end == offset else (text[offset:end], end)


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
    """Inline destinations and reference-label uses by line index, plus every
    destination defined for each normalized label, in document order."""
    inline: dict[int, list[str]] = field(default_factory=dict)
    uses: dict[int, list[str]] = field(default_factory=dict)
    definitions: dict[str, list[str]] = field(default_factory=dict)
    uncertain: bool = False


def _label_close(text: str, offset: int) -> int | None:
    """Return the offset of the ``]`` closing a link label opened at ``offset``."""
    end = offset + 1
    limit = min(len(text), offset + _MAX_LABEL + 2)
    while end < limit and text[end] != '[':
        if text[end] == ']':
            return end
        end += 2 if _escaped(text, end) else 1
    return None


def _definition_label(text: str, offset: int) -> int | None:
    """Return the closing bracket offset if a ``[label]:`` starts at ``offset``."""
    close = _label_close(text, offset) if text.startswith('[', offset) else None
    return close if close is not None and text.startswith(':', close + 1) and text[offset + 1:close].strip() else None


def _definition_end(text: str, offset: int, close: int, first_line: int, starts: list[int], links: _Links,
                    unclosed: set[str]) -> int | None:
    """Record the definition whose label spans ``offset`` to ``close`` and
    return the offset after it, or None if its destination or title does not parse."""
    destination, end = _destination(text, _skip_space(text, close + 2))
    if destination is None:
        return None
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
    label = _label(text[offset + 1:close])
    # CommonMark uses the first definition of a label. This tokenizer cannot
    # always tell which line that is: it does not parse HTML blocks, and it
    # compares labels more loosely. Every distinct destination is therefore
    # kept, so no earlier look-alike can hide the one that takes effect.
    destinations = links.definitions.setdefault(label, [])
    if destination not in destinations:
        if len(destinations) < _MAX_DEFINITIONS:
            destinations.append(destination)
        else:
            links.uncertain = True
    # A definition also counts as a use of its label, so a defined helper is
    # governed even when no link in the document refers to it.
    links.uses.setdefault(first_line + bisect_right(starts, offset) - 1, []).append(label)
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
        close = _definition_label(text, offset)
        end = None if close is None else _definition_end(text, offset, close, first_line, starts, links, unclosed)
        if end is None:
            break
        offset = end
    # A definition cannot interrupt a paragraph, so CommonMark reads these
    # lines as text. Other renderers accept them, so they are recorded too.
    for start in starts[bisect_right(starts, offset) - 1:]:
        close = _definition_label(text, start) if start >= offset else None
        if close is not None and _definition_end(text, start, close, first_line, starts, links, unclosed) is None:
            links.uncertain = True  # Shaped like a definition, with a destination that does not parse.
    openers: list[tuple[int, bool]] = []
    # Failed destination scans in ordinary prose end at the next space and do
    # not overlap. Crafted nesting makes them overlap up to _MAX_PARENS deep, so
    # past this allowance the block stops trying; it is already incomplete.
    budget = 2 * len(text) + 1024
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
        if text.startswith('(', offset) and budget < 0:
            links.uncertain = True
        elif text.startswith('(', offset):
            start = _skip_space(text, offset + 1)
            destination, end = ('', start) if text.startswith(')', start) else _destination(text, start)
            if destination is None:
                budget -= end - start
            else:
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
        if not nested and offset - opened - 2 <= _MAX_LABEL:
            raw = text[opened + 1:offset - 1]
            if raw.strip():
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
    uncertain |= links.uncertain or _FOREIGN_LINE_BREAK.search(body) is not None
    if '`' in body:
        # Definitions are block structure and bind before inline code, but
        # spans are masked first here; a backtick on such a line, or inside an
        # HTML comment, can pair with a later one and hide what lies between.
        uncertain |= any('`' in line and (_definition_label(line, 0) is not None or _BACKTICK_IN_ANGLE.search(line)) for line in content)
        uncertain |= any('`' in comment.partition('-->')[0] for comment in body.split('<!--')[1:])
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
        candidates.extend((_plain(path[0]), 'resource') for m in _DIRECTIVE.finditer(line) if (path := _DIRECTIVE_PATH.match(m[1])))
        candidates.extend((_decode(raw), 'link') for label in links.uses.get(index, [])
                          for raw in links.definitions.get(label, ()) if raw)
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
