"""Validation exit-code precedence over merged diagnostics."""
from __future__ import annotations

from pathlib import Path

import pytest

from tracemantle.gate import compute_exit_code
from tracemantle.result import Diagnostic, Severity, ValidationResult


def _result(*diagnostics: tuple[str, Severity]) -> ValidationResult:
    return ValidationResult(Path('SKILL.md'), [Diagnostic(rule, severity, 'message') for rule, severity in diagnostics])


@pytest.mark.parametrize('diagnostics,strict,expected', [
    ((), False, 0),
    ((('sizing.lines', Severity.WARNING),), False, 0),
    ((('sizing.lines', Severity.WARNING),), True, 1),
    ((('semantic.contradiction.detected', Severity.ERROR),), False, 3),
    ((('semantic.contradiction.detected', Severity.ERROR), ('frontmatter.name.required', Severity.ERROR)), False, 1),
    ((('semantic.ingest.parse_error', Severity.ERROR),), False, 1),
    ((('graph.contradiction.found', Severity.ERROR),), False, 1),
    ((('semantic.contradiction.detected', Severity.INFO),), True, 0),
], ids=['clean', 'warning', 'strict-warning', 'semantic-only', 'symbolic-beats-semantic', 'ingest-failure',
        'graph-contradiction', 'info-only'])
def test_exit_code_precedence(diagnostics: tuple[tuple[str, Severity], ...], strict: bool, expected: int) -> None:
    assert compute_exit_code([_result(*diagnostics)], strict_all=strict) == expected
