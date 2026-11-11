"""Resource checks use the shared Markdown tokens and actual reference chains."""
from __future__ import annotations

from tracemantle.dependencies import analyze_dependencies
from tracemantle.parser import ParsedSkill
from tracemantle.result import Diagnostic


def check_dependencies(skill: ParsedSkill) -> list[Diagnostic]:
    return list(analyze_dependencies(skill.path, skill.markdown, reference_format=skill.settings.reference_format).diagnostics)
