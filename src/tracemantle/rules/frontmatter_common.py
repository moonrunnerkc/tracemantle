from __future__ import annotations

import re

from tracemantle.parser import ParsedSkill
from tracemantle.template_detection import is_template

# Detects ``## name:`` style markdown headings inside the frontmatter block.
# The heading variant is what fails: PyYAML drops the leading ``#`` as a
# comment, so the field never lands in the parsed mapping.
# Horizontal whitespace only, so a match cannot span lines and each line start
# scans only its own line.
_FRONTMATTER_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+(\w+)[ \t]*:", re.MULTILINE)


def _heading_for_field(yaml_text: str, field: str) -> bool:
    """Return True when ``field`` appears as a ``## name:`` markdown heading.

    Only the parsed frontmatter text is scanned, so body headings and the
    delimiter rules stay exactly those of the parser.
    """
    return any(match.group(1) == field for match in _FRONTMATTER_HEADING_RE.finditer(yaml_text))


def _markdown_heading_hint(field: str) -> str:
    """Return the appended hint for a ``## field:`` heading inside frontmatter."""
    return (
        f" hint: found '## {field}:' as a markdown heading inside frontmatter. "
        f"Frontmatter keys are YAML, not markdown. Use '{field}: value' (no '##')."
    )


def name_directory_mismatch(skill: ParsedSkill) -> tuple[str, str] | None:
    """Return ``(name, parent_dir)`` when a non-template skill's name differs
    from its directory, else None. Templates are skipped because placeholder
    files are not meant to deploy."""
    name = skill.frontmatter.get("name")
    if name is None or not str(name) or is_template(skill):
        return None
    parent_dir = skill.path.parent.name
    return (str(name), parent_dir) if parent_dir and parent_dir != str(name) else None
