"""Markdown report cells must render as written in a GFM table."""
from __future__ import annotations

from pathlib import Path

from tracemantle.formatters import _format_markdown
from tracemantle.result import Diagnostic, Severity, ValidationResult


def _row(diagnostic: Diagnostic) -> str:
    report = _format_markdown([ValidationResult(Path('demo/SKILL.md'), [diagnostic])])
    return next(line for line in report.splitlines() if line.startswith('| 3 |'))


def test_pipe_in_a_message_is_escaped_once_and_keeps_the_row_intact() -> None:
    row = _row(Diagnostic('references.broken', Severity.ERROR, 'Broken reference: a|b.md', line=3))
    assert 'a\\|b.md' in row
    assert 'a\\\\|b.md' not in row
    unescaped_pipes = row.replace('\\|', '').count('|')
    assert unescaped_pipes == 7


def test_rule_ids_in_code_spans_carry_no_markdown_backslashes() -> None:
    row = _row(Diagnostic('semantic.ingest.graph_parse_error', Severity.ERROR, 'Bad graph.', line=3))
    assert '`semantic.ingest.graph_parse_error`' in row
