"""Resource checks use the shared Markdown tokens and actual reference chains."""
from __future__ import annotations

from tracemantle.dependencies import analyze_dependencies
from tracemantle.markdown import tokenize
from tracemantle.parser import ParsedSkill
from tracemantle.result import Diagnostic


def _extract_references(body: str) -> list[str]:
    return [r.target for r in tokenize(body).resources if r.kind in {'link', 'resource'}]


def check_dependencies(skill: ParsedSkill) -> list[Diagnostic]:
    return list(analyze_dependencies(skill.path, skill.markdown).diagnostics)


def check_broken_references(skill: ParsedSkill) -> list[Diagnostic]:
    return [d for d in check_dependencies(skill) if d.rule != 'references.depth-exceeded']


def check_reference_depth(skill: ParsedSkill) -> list[Diagnostic]:
    return [d for d in check_dependencies(skill) if d.rule == 'references.depth-exceeded']


def _reference_depth(ref_path: str) -> int:
    """Legacy path-nesting helper; validation measures reference chains instead."""
    from pathlib import Path
    return max(0, len(Path(ref_path).parts) - 1)
