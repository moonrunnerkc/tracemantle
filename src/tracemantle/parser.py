from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from tracemantle.io_limits import (
    MAX_SKILL_BYTES,
    MAX_YAML_ALIASES,
    MAX_YAML_DEPTH,
    MAX_YAML_NODES,
    read_bounded_bytes,
)
from tracemantle.markdown import Markdown, tokenize


class ParseError(Exception):
    """Invalid or unreadable skill input, with an optional full-file location."""

    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


@dataclass(frozen=True, slots=True)
class DocumentSettings:
    extension_fields: frozenset[str] = frozenset()
    reserved_words: tuple[str, ...] = ('anthropic', 'claude')
    tokenizer: str = 'heuristic'


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class ParsedSkill:
    path: Path
    frontmatter: Mapping[str, Any]
    body: str
    body_lines: int
    raw_text: str
    body_start_line: int = 1
    yaml_text: str = ''
    field_lines: Mapping[str, int] = field(default_factory=dict)
    yaml_anchors: tuple[str, ...] = ()
    settings: DocumentSettings = DocumentSettings()
    raw_bytes: bytes = field(default=b"", repr=False)
    markdown: Markdown = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'frontmatter', _freeze(dict(self.frontmatter)))
        object.__setattr__(self, 'field_lines', MappingProxyType(dict(self.field_lines)))
        object.__setattr__(self, 'markdown', tokenize(self.body, self.body_start_line))


class _Loader(yaml.SafeLoader):
    def __init__(self, stream: str):
        super().__init__(stream)
        self.depth = 0
        self.nodes = 0
        self.alias_count = 0
        self.anchor_names: set[str] = set()
        self.field_lines: dict[str, int] = {}

    def compose_node(self, parent: Any, index: Any) -> Any:
        event = self.peek_event()  # type: ignore[no-untyped-call]  # PyYAML event access lacks stubs.
        self.nodes += 1
        self.depth += 1
        if isinstance(event, yaml.AliasEvent):
            self.alias_count += 1
        if getattr(event, 'anchor', None):
            self.anchor_names.add(event.anchor)
        if self.depth > MAX_YAML_DEPTH or self.nodes > MAX_YAML_NODES or self.alias_count > MAX_YAML_ALIASES:
            raise ParseError('YAML depth, node or alias limit exceeded. Simplify the frontmatter.', event.start_mark.line + 2)
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_object(self, node: yaml.Node, deep: bool = False) -> Any:
        try:
            return super().construct_object(node, deep=deep)
        except ValueError as exc:
            # PyYAML's numeric/date constructors use Python conversions that
            # can reject scalar input without raising a YAMLError.
            if node.tag not in {'tag:yaml.org,2002:int', 'tag:yaml.org,2002:float', 'tag:yaml.org,2002:timestamp'}:
                raise
            kind = node.tag.rsplit(':', 1)[-1]
            raise ParseError(
                f'Invalid YAML {kind} scalar: {str(exc)[:240]}. Correct the value or quote literal text.',
                node.start_mark.line + 2,
            ) from exc

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        result: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            if key_node.tag != 'tag:yaml.org,2002:str':
                raise ParseError('YAML mapping keys must be strings; quote the key. Merge keys are unsupported.', key_node.start_mark.line + 2)
            key = self.construct_object(key_node, deep=True)
            if key in result:
                raise ParseError(f"Duplicate YAML key '{key}'. Keep one value per key.", key_node.start_mark.line + 2)
            result[key] = self.construct_object(value_node, deep=True)
            if node.start_mark.column == 0:
                self.field_lines[key] = key_node.start_mark.line + 2
        return result


def parse(path: Path, *, settings: DocumentSettings | None = None, max_bytes: int = MAX_SKILL_BYTES) -> ParsedSkill:
    """Read once; standalone delimiter lines delimit YAML. BOM/CRLF are accepted."""
    settings = settings or DocumentSettings()
    raw = read_bounded_bytes(path, max_bytes=min(max_bytes, MAX_SKILL_BYTES), what='SKILL.md', error_cls=ParseError)
    try:
        text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    except UnicodeDecodeError as exc:
        raise ParseError(f'File is not valid UTF-8: {path}') from exc
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip(' \t\n') != '---':
        return ParsedSkill(path, {}, text, len(text.splitlines()), text, settings=settings, raw_bytes=raw)
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip(' \t\n') == '---'), None)
    if end is None:
        raise ParseError(f'Unterminated frontmatter in {path}. Put the closing --- on its own line.', 1)
    yaml_text = ''.join(lines[1:end])
    loader = _Loader(yaml_text)
    try:
        loaded = loader.get_single_data()
    except (yaml.YAMLError, RecursionError) as exc:
        mark = getattr(exc, 'problem_mark', None)
        raise ParseError(f'Invalid YAML frontmatter in {path}: {exc}', mark.line + 2 if mark else None) from exc
    finally:
        loader.dispose()
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ParseError(f'Frontmatter must be a YAML mapping, got {type(loaded).__name__} in {path}. Wrap frontmatter in key: value pairs.', 2)
    # Count expanded alias structure before freezing or rendering it.
    pending = [(loaded, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > MAX_YAML_DEPTH or nodes > MAX_YAML_NODES:
            raise ParseError('Expanded YAML alias structure exceeds its depth/node limit.', 2)
        if isinstance(value, (dict, list)):
            pending.extend((item, depth + 1) for item in (value.values() if isinstance(value, dict) else value))
    body = ''.join(lines[end + 1:])
    return ParsedSkill(path, loaded, body, len(body.splitlines()), text, end + 2, yaml_text,
                       loader.field_lines, tuple(sorted(loader.anchor_names)), settings, raw)
