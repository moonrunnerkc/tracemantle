"""Markdown classification for the heuristic capability graph: which
headings name inputs, outputs or imperative capabilities, and how list items
and backtick references become node names.

The vocabularies are conservative by design. The agent-mode extractor handles
the long tail; the heuristic errs toward precision over recall.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Literal

IMPERATIVE_VERBS: tuple[str, ...] = (
    "analyze",
    "build",
    "check",
    "compile",
    "configure",
    "convert",
    "create",
    "define",
    "describe",
    "design",
    "document",
    "evaluate",
    "explain",
    "extract",
    "find",
    "format",
    "generate",
    "identify",
    "implement",
    "install",
    "list",
    "parse",
    "plan",
    "render",
    "review",
    "run",
    "set",
    "setup",
    "study",
    "summarize",
    "test",
    "transform",
    "understand",
    "validate",
    "write",
)

# Section prefixes stripped from headings before imperative-verb classification.
# Matches "Phase 1:", "Phase 1 -", "Step 2.", "Section 3:", "1.", "2)",
# "1.1", "1.1.1 ", "1.2)" etc. Real-world skills use both flat and nested
# numbering (mcp-builder uses "#### 1.1 Understand...").  Conservative:
# strips a single leading section/numeric token plus its trailing delimiter
# or whitespace, leaving the rest of the heading intact for verb detection.
_SECTION_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:
        (?:phase|step|section|part|chapter)\s+[\w\.]+\s*[:.\-]?\s+  # named section
        | \d+(?:\.\d+)*\s*[:.)\-]?\s+                               # numeric (incl. 1.1)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

INPUT_SECTION_ALIASES: tuple[str, ...] = (
    "before you start",
    "inputs",
    "prerequisites",
    "requirements",
    "setup",
)

OUTPUT_SECTION_ALIASES: tuple[str, ...] = (
    "output",
    "outputs",
    "produces",
    "result",
    "results",
    "returns",
)


def _normalize_heading(text: str) -> str:
    """Lower-case and strip non-alpha characters for alias matching."""
    return re.sub(r"[^a-z\s]", "", text.lower()).strip()


def _is_input_section_heading(text: str) -> bool:
    """Return True if heading text matches an input-section alias."""
    return _normalize_heading(text) in INPUT_SECTION_ALIASES


def _is_output_section_heading(text: str) -> bool:
    """Return True if heading text matches an output-section alias."""
    return _normalize_heading(text) in OUTPUT_SECTION_ALIASES


def _strip_section_prefix(text: str) -> str:
    """Strip a single leading section or numeric prefix.

    Real-world skills frequently nest imperative verbs inside section labels
    like "Phase 1: Implement Tools" or "2. Build the index". The verb-classifier
    needs the prefix removed so the first word seen is the actual verb.
    Returns the text unchanged when no recognized prefix is present.
    """
    return _SECTION_PREFIX_RE.sub("", text, count=1)


def _is_imperative_heading(text: str) -> bool:
    """Return True if the heading's first word is a known imperative verb.

    Section/numeric prefixes ("Phase 1:", "Step 2.", "1.") are stripped first
    so that headings like "Phase 1: Implement Tools" classify on "Implement".
    """
    stripped = _strip_section_prefix(text)
    first_word = stripped.lower().split()[0] if stripped.split() else ""
    return first_word in IMPERATIVE_VERBS


def _infer_input_kind(
    item_text: str,
) -> Literal["file", "tool", "env", "context", "prerequisite"]:
    """Infer Input.kind from a list-item text string.

    Checks in order: env (ALL_CAPS), file (extension or path), tool (backtick
    single-token), prerequisite (fallback).

    Args:
        item_text: Text of the list item after stripping the list marker.

    Returns:
        The inferred input kind.
    """
    name_raw = re.split(r"\s+[-:]\s+", item_text, maxsplit=1)[0].strip()
    name = name_raw.strip("`").strip()

    # env: ALL_CAPS with underscores/digits, at least 2 characters, no extension.
    if re.fullmatch(r"[A-Z][A-Z0-9_]{1,}", name) and "." not in name:
        return "env"

    # file: has a path separator or a recognizable file extension.
    if "/" in name or "\\" in name or re.search(r"\.\w{1,6}$", name):
        return "file"

    # tool: originally backtick-quoted and single-token (no spaces in name).
    if name_raw.startswith("`") and " " not in name:
        return "tool"

    return "prerequisite"


def _infer_output_kind(
    item_text: str,
) -> Literal["file", "artifact", "side_effect", "return"]:
    """Infer Output.kind from a list-item text string.

    Checks in order: file (extension or path), side_effect (mutating verb),
    return (short single-token), artifact (fallback).

    Args:
        item_text: Text of the list item after stripping the list marker.

    Returns:
        The inferred output kind.
    """
    name_raw = re.split(r"\s+[-:]\s+", item_text, maxsplit=1)[0].strip()
    name = name_raw.strip("`").strip()
    full = item_text.lower()

    # file: has a path separator or recognizable file extension.
    if "/" in name or "\\" in name or re.search(r"\.\w{1,6}$", name):
        return "file"

    # side_effect: description mentions a mutating verb.
    if re.search(r"\b(modif|updat|delet|overwrit|sends?\b|emit|writes?\b)", full):
        return "side_effect"

    # return: short single-token name (no spaces), value-shaped.
    if " " not in name and len(name) <= 30:
        return "return"

    return "artifact"


def extract_backtick_refs(text: str) -> list[str]:
    """Return all backtick-quoted strings found in text, in order.

    Args:
        text: Arbitrary markdown body text.

    Returns:
        Contents of each backtick span.
    """
    return re.findall(r"`([^`]+)`", text)


def _extract_list_item_name(item_text: str) -> str:
    """Return the canonical node name from a list item (description stripped)."""
    name_raw = re.split(r"\s+[-:]\s+", item_text, maxsplit=1)[0].strip()
    return name_raw.strip("`").strip()


def _get_list_item(line: str) -> str | None:
    """Return item text if the line is a list item, else None."""
    m = re.match(r"^\s*(?:-|\*|\d+\.)\s+(.*)", line)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Body section parser
# ---------------------------------------------------------------------------


def _sectionize(
    body_lines: list[str],
) -> list[tuple[int, int, str, list[tuple[int, str]]]]:
    """Split body into sections.

    Each section is (start_line_1indexed, level, heading_text, content_lines).
    content_lines is [(line_num, text)] for every line between this heading
    and the next heading at the same or shallower level. Sub-headings are
    included in content so that nested list items are still harvested.

    Args:
        body_lines: Body of the skill as a list of line strings (no trailing newlines).

    Returns:
        List of section tuples in document order.
    """
    headings: list[tuple[int, int, str]] = []
    for i, line in enumerate(body_lines, 1):
        m = re.match(r"^(#+)\s+(.*)", line)
        if m:
            headings.append((i, len(m.group(1)), m.group(2).strip()))

    sections = []
    for idx, (line_num, level, text) in enumerate(headings):
        content_end = len(body_lines) + 1
        for j in range(idx + 1, len(headings)):
            if headings[j][1] <= level:
                content_end = headings[j][0]
                break
        content = [(i, body_lines[i - 1]) for i in range(line_num + 1, content_end)]
        sections.append((line_num, level, text, content))

    return sections


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------


def _named_list_items(content: list[tuple[int, str]]) -> Iterator[tuple[int, str, str]]:
    """Yield ``(line, name, item_text)`` for each list item with a usable name."""
    for line, text in content:
        item = _get_list_item(text)
        if item is None:
            continue
        name = _extract_list_item_name(item)
        if name:
            yield line, name, item
