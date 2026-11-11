"""SARIF 2.1.0 output for validation results, for code-scanning uploads."""

from __future__ import annotations

import json
from pathlib import PurePath
from urllib.parse import quote

from tracemantle.result import Severity, ValidationResult

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_LEVELS = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "note"}


def _artifact_uri(path: PurePath) -> str:
    """Return a URI reference for ``path``: absolute paths become ``file:``
    URIs and relative paths stay relative, so code scanning can resolve them
    against the checkout."""
    if path.is_absolute():
        return path.as_uri()
    return quote(path.as_posix())


def format_sarif(results: list[ValidationResult], version: str, *, gate_exit_code: int) -> str:
    """Render validation results as one SARIF 2.1.0 log with a single run.

    Every diagnostic becomes a result: ERROR maps to ``error``, WARNING to
    ``warning`` and INFO to ``note``. Diagnostics without a line carry only the
    artifact location. Message text is preserved as data; JSON escaping makes
    untrusted control characters inert. The run's invocation records the gate
    exit code so an uploaded log states whether the batch passed.

    Args:
        results: Merged, ignore-filtered validation results.
        version: TraceMantle version for the tool driver.
        gate_exit_code: The exit code this invocation returns.

    Returns:
        The SARIF log as indented JSON.
    """
    rules: dict[str, dict[str, object]] = {}
    sarif_results: list[dict[str, object]] = []
    for result in results:
        uri = _artifact_uri(result.path)
        for diagnostic in result.diagnostics:
            rules.setdefault(diagnostic.rule, {"id": diagnostic.rule, "shortDescription": {"text": diagnostic.rule}})
            physical: dict[str, object] = {"artifactLocation": {"uri": uri}}
            if diagnostic.line is not None:
                physical["region"] = {"startLine": diagnostic.line}
            sarif_results.append({
                "ruleId": diagnostic.rule,
                "level": _LEVELS[diagnostic.severity],
                "message": {"text": diagnostic.message},
                "locations": [{"physicalLocation": physical}],
                "properties": {"source": diagnostic.source, "confidence": diagnostic.confidence},
            })
    log = {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "TraceMantle",
                "version": version,
                "informationUri": "https://github.com/moonrunnerkc/tracemantle",
                "rules": [rules[rule_id] for rule_id in sorted(rules)],
            }},
            "invocations": [{"executionSuccessful": True, "exitCode": gate_exit_code}],
            "results": sarif_results,
        }],
    }
    return json.dumps(log, indent=2)
