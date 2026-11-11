"""Cross-agent compatibility warnings for SKILL.md.

The agentskills.io spec is consumed by Claude Code, VS Code/Copilot,
OpenAI Codex, Cursor, and other agents. Implementation-specific fields
work in one agent but are ignored or cause breakage in others.

This module flags fields with limited cross-agent support so authors
can make informed decisions about portability.

Provenance dates (``_CLAUDE_DATA_DATE``, ``_CODEX_DATA_DATE``,
``_VSCODE_DATA_DATE``, ``_CURSOR_DATA_DATE``) record when historical claims were
recorded, not runtime verification. The ``test_compat_data_freshness``
test asserts that these dates are within 365 days of today; when the test
fails, record new source and runtime evidence before changing a claim.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from tracemantle import config
from tracemantle.parser import ParsedSkill
from tracemantle.result import Diagnostic, Severity
from tracemantle.rules.frontmatter_common import name_directory_mismatch

# ---------------------------------------------------------------------------
# Provenance dates for compatibility data
# ---------------------------------------------------------------------------

_CLAUDE_DATA_DATE = "2026-04-20"
_CODEX_DATA_DATE = "2026-04-20"
_VSCODE_DATA_DATE = "2026-04-20"
_CURSOR_DATA_DATE = "2026-04-20"

# Detects a block scalar marker (>, >+, |, |+) on the description field.
# >- and |- strip trailing whitespace and render correctly in Cursor's UI,
# so they are deliberately excluded from the unsafe-marker group.
_CURSOR_UNSAFE_DESC_BLOCK_SCALAR = re.compile(
    r"^description\s*:\s*(?P<marker>[>|]\+?)\s*(?:#.*)?$",
    re.MULTILINE,
)


def check_claude_only_fields(skill: ParsedSkill) -> list[Diagnostic]:
    """Flag fields that only work in Claude Code."""
    diagnostics: list[Diagnostic] = []
    for field in skill.frontmatter:
        if field in config.CLAUDE_ONLY_FIELDS:
            diagnostics.append(Diagnostic(
                rule="compat.claude-only",
                severity=Severity.INFO,
                message=(
                    f"Field '{field}' is Claude Code-specific "
                    f"(as of {_CLAUDE_DATA_DATE}). "
                    f"Runtime applicability is unverified in VS Code/Copilot; behavior in "
                    f"Codex and Cursor is unverified."
                ),
            ))
    return diagnostics


def _vscode_dirname_rule(severity: Severity) -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Build the VS Code name/directory rule at ``severity``. The ERROR variant
    (--strict-vscode) states the consequence as certain rather than likely."""
    outcome = "will not" if severity == Severity.ERROR else "would not"

    def check(skill: ParsedSkill) -> list[Diagnostic]:
        pair = name_directory_mismatch(skill)
        if pair is None:
            return []
        name, parent_dir = pair
        return [Diagnostic(
            rule="compat.vscode-dirname",
            severity=severity,
            message=(
                f"VS Code requires the name field ('{name}') to match the "
                f"parent directory ('{parent_dir}'). This skill {outcome} "
                f"conform to the standard naming contract; loader behavior is unverified (historical profile {_VSCODE_DATA_DATE})."
            ),
        )]

    return check


# INFO note that complements the ERROR-level frontmatter.name.directory-mismatch
# check, which --skip-dirname-check can disable. --strict-vscode promotes it.
check_vscode_dirname = _vscode_dirname_rule(Severity.INFO)
check_vscode_dirname.__name__ = "check_vscode_dirname"


def check_unverified_fields(skill: ParsedSkill) -> list[Diagnostic]:
    """Note fields whose behavior in Codex and Cursor is unverified."""
    diagnostics: list[Diagnostic] = []
    for field in skill.frontmatter:
        compat = config.COMPAT_MATRIX.get(field)
        if compat is None:
            continue
        unknown_agents = [
            agent for agent, status in compat.items()
            if status == "unknown"
        ]
        if unknown_agents:
            agents_str = ", ".join(sorted(unknown_agents))
            # Provenance: attach dates for agents with "unknown" status
            date_parts = []
            if "codex" in [a.lower() for a in unknown_agents]:
                date_parts.append(f"Codex: {_CODEX_DATA_DATE}")
            if "cursor" in [a.lower() for a in unknown_agents]:
                date_parts.append(f"Cursor: {_CURSOR_DATA_DATE}")
            date_suffix = ""
            if date_parts:
                date_suffix = f" (as of {'; '.join(date_parts)})"
            diagnostics.append(Diagnostic(
                rule="compat.unverified",
                severity=Severity.INFO,
                message=(
                    f"Behavior of field '{field}' in {agents_str} is unverified{date_suffix}."
                ),
            ))
    return diagnostics


def make_strict_vscode_rule() -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule that promotes VS Code compat issues to ERROR severity."""
    rule = _vscode_dirname_rule(Severity.ERROR)
    rule.__name__ = "check_strict_vscode"
    return rule


def _detect_cursor_unsafe_block_scalar(skill: ParsedSkill) -> str | None:
    """Return the offending block-scalar marker on description, else None.

    PyYAML's safe_load discards the scalar style indicator, so we re-scan the
    raw frontmatter block. The simpler regex path avoids switching the parser
    to yaml.compose() and reaches into node attributes from every rule.
    """
    block = skill.yaml_text
    marker_match = _CURSOR_UNSAFE_DESC_BLOCK_SCALAR.search(block)
    if marker_match is None:
        return None
    return marker_match.group("marker")


def _cursor_block_scalar_message(marker: str) -> str:
    """Return the diagnostic message for an unsafe Cursor block scalar."""
    return (
        f"description uses block scalar '{marker}' which Cursor's skills "
        f"UI historically rendered as empty in an unversioned report (got 'description: {marker}'). Runtime behavior is unverified. Consider "
        f"'description: >-' (folded strip) instead "
        f"(as of {_CURSOR_DATA_DATE})."
    )


def _cursor_block_scalar_rule(severity: Severity) -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Build the Cursor block-scalar rule at ``severity``: INFO by default,
    WARNING for --target-agent cursor, ERROR for --strict-cursor."""

    def check(skill: ParsedSkill) -> list[Diagnostic]:
        marker = _detect_cursor_unsafe_block_scalar(skill)
        if marker is None:
            return []
        return [Diagnostic(
            rule="compat.cursor-description-block-scalar",
            severity=severity,
            message=_cursor_block_scalar_message(marker),
        )]

    return check


check_cursor_description_block_scalar = _cursor_block_scalar_rule(Severity.INFO)
check_cursor_description_block_scalar.__name__ = "check_cursor_description_block_scalar"
check_cursor_description_block_scalar_warning = _cursor_block_scalar_rule(Severity.WARNING)
check_cursor_description_block_scalar_warning.__name__ = "check_cursor_description_block_scalar_warning"


def make_strict_cursor_rule() -> Callable[[ParsedSkill], list[Diagnostic]]:
    """Return a rule that promotes Cursor block-scalar issues to ERROR."""
    rule = _cursor_block_scalar_rule(Severity.ERROR)
    rule.__name__ = "check_strict_cursor"
    return rule
