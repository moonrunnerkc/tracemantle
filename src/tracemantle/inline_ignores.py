"""Per-file rule suppression declared in a skill's own frontmatter.

A YAML comment such as ``# tracemantle: ignore=sizing, compat.unverified``
inside the frontmatter suppresses diagnostics whose rule starts with a listed
prefix, for that file only. A comment keeps the parsed frontmatter, and so
what an agent loads, unchanged. The directive is reviewed skill content, like
project configuration: it is always reported as an ``ignore.inline`` note so a
suppression is never silent, and it cannot suppress its own ``ignore.`` reports.
"""

from __future__ import annotations

import re

from tracemantle.parser import ParsedSkill
from tracemantle.result import Diagnostic, Severity

_DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*tracemantle:[ \t]*ignore[ \t]*=([^\n]*)$", re.MULTILINE)
_PREFIX = re.compile(r"[a-z0-9][a-z0-9._-]*")
_OWN_NAMESPACE = "ignore."


def _directive_tokens(skill: ParsedSkill) -> list[str]:
    return [token.strip() for match in _DIRECTIVE.finditer(skill.yaml_text) for token in match[1].split(",") if token.strip()]


def _is_usable(token: str) -> bool:
    return _PREFIX.fullmatch(token) is not None and not _OWN_NAMESPACE.startswith(token) and not token.startswith(_OWN_NAMESPACE)


def inline_ignore_prefixes(skill: ParsedSkill) -> tuple[str, ...]:
    """Return the usable rule prefixes from the skill's inline ignore comments,
    deduplicated in declaration order. Malformed tokens and any that would
    reach the ``ignore.`` namespace are excluded; check_inline_ignores reports them."""
    return tuple(dict.fromkeys(token for token in _directive_tokens(skill) if _is_usable(token)))


def check_inline_ignores(skill: ParsedSkill) -> list[Diagnostic]:
    """Report each inline ignore directive: a note listing what it suppresses,
    and a warning for every token that cannot be used as a rule prefix."""
    tokens = _directive_tokens(skill)
    diagnostics = [
        Diagnostic(
            rule="ignore.inline-invalid",
            severity=Severity.WARNING,
            message=(
                f"Inline ignore token {token!r} is not a usable rule prefix. Use lowercase rule IDs or prefixes "
                f"such as 'sizing' or 'compat.unverified'; 'ignore.' reports cannot be suppressed inline."
            ),
        )
        for token in dict.fromkeys(tokens) if not _is_usable(token)
    ]
    prefixes = inline_ignore_prefixes(skill)
    if prefixes:
        diagnostics.append(Diagnostic(
            rule="ignore.inline",
            severity=Severity.INFO,
            message=f"Inline ignore suppresses rules starting with: {', '.join(prefixes)}. Remove the frontmatter comment to restore them.",
        ))
    return diagnostics
