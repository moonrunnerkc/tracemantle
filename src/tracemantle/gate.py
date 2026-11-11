"""The validation gate: which diagnostics count and what exit code they produce."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from tracemantle.result import Severity, ValidationResult


def compute_exit_code(results: list[ValidationResult], *, strict_all: bool) -> int:
    """Return the process exit code from the merged results.

    Any error outside the ``semantic.`` namespace, or a ``semantic.ingest.``
    failure, is 1. A run whose only errors are semantic contradictions from a
    critique ingest is 3. A warning-only run is 0 unless ``--strict`` escalates
    it to 1. Exit 2 stays reserved for tool misuse and input errors.
    """
    errors = [d.rule for r in results for d in r.diagnostics if d.severity == Severity.ERROR]
    if any(not rule.startswith("semantic.") or rule.startswith("semantic.ingest.") for rule in errors):
        return 1
    if errors:
        return 3
    if strict_all and any(d.severity == Severity.WARNING for r in results for d in r.diagnostics):
        return 1
    return 0


def filter_results(results: list[ValidationResult], prefixes: list[str],
                   inline: Mapping[Path, tuple[str, ...]] | None = None) -> list[ValidationResult]:
    """Drop diagnostics whose rule starts with any ``--ignore`` prefix, or with
    one of the file's own inline ignore prefixes from ``inline``. Inline
    prefixes never drop ``ignore.`` diagnostics, which report the suppression."""
    inline = inline or {}

    def kept(rule: str, file_prefixes: tuple[str, ...]) -> bool:
        if any(rule.startswith(prefix) for prefix in prefixes):
            return False
        return rule.startswith("ignore.") or not any(rule.startswith(prefix) for prefix in file_prefixes)

    return [replace(r, diagnostics=[d for d in r.diagnostics if kept(d.rule, inline.get(r.path, ()))]) for r in results]
