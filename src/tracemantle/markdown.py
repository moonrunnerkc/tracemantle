"""A bounded Markdown resource tokenizer shared by analysis and manifests.

This deliberately supports a documented subset, not HTML or Markdown execution.
Unsupported dynamic references remain unknown dependencies in bundle reports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|(?:[^\s()\\]|\\.|\([^()\n]*\))+)\s*(?:[\"\x27][^\n]*?[\"\x27]\s*)?\)')
_DEFINITION = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)')
_REFERENCE = re.compile(r'\[([^\]\n]+)\](?:\[([^\]\n]*)\])?')
_HTML = re.compile(r'<(?:a|img)\s+[^>]*?(?:href|src)\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]', re.I)
_INLINE = re.compile(r'(`+)([^`\n]+)\1')
_DIRECTIVE = re.compile(r'(?:source|file|include):\s*([^\s]+\.[a-zA-Z0-9]+)', re.I)


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


def tokenize(body: str, start_line: int = 1) -> Markdown:
    visible: list[str] = []
    fence = ''
    for line in body.splitlines():
        match = _FENCE.match(line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = ''
            visible.append('')
        elif match:
            fence = match[1]
            visible.append('')
        else:
            visible.append(line)
    definitions = {m[1].casefold(): m[2] for line in visible if (m := _DEFINITION.match(line))}
    resources: list[Resource] = []
    headings: list[tuple[int, int, str]] = []
    seen: set[tuple[str, str]] = set()
    uncertain = False
    for number, line in enumerate(visible, start_line):
        heading = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading:
            headings.append((number, len(heading[1]), heading[2]))
        candidates = [(m[1], 'link') for m in _LINK.finditer(line)]
        candidates.extend((m[1], 'link') for m in _HTML.finditer(line))
        candidates.extend((m[1], 'resource') for m in _DIRECTIVE.finditer(line))
        for m in _REFERENCE.finditer(line):
            label = (m[2] or m[1]).casefold()
            if label in definitions:
                candidates.append((definitions[label], 'link'))
        for m in _INLINE.finditer(line):
            target = m[2].strip()
            if '/' in target and not any(c.isspace() for c in target):
                candidates.append((target, 'resource'))
            elif re.fullmatch(r'[\w.-]+\.[a-zA-Z0-9]+', target):
                candidates.append((target, 'generated'))
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
