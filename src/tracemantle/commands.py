"""The default validation pipeline for the tracemantle CLI.

`cli.py` owns argument wiring and dispatch. Input resolution lives in
`cli_inputs`, emit modes in `emit_modes` and history in `history_commands`.
This module validates a batch, merges ingest and graph diagnostics, records
history when requested, prints the report and exits with the gate's code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from tracemantle import __version__
from tracemantle.agents.graph_parser import GraphParseError
from tracemantle.agents.parser import CritiqueParseError
from tracemantle.cli_inputs import parse_batch, read_ingest_raw
from tracemantle.core import (
    extract_graph_agent,
    extract_graph_heuristic,
    ingest_critique_response,
    merge_diagnostics,
    run_divergence_analyzers,
    run_graph_analyzers,
    validate,
)
from tracemantle.core.graph import GraphLimitError
from tracemantle.formatters import (
    _format_agent,
    _format_github,
    _format_json,
    _format_markdown,
    _format_text,
)
from tracemantle.gate import compute_exit_code, filter_results
from tracemantle.history_commands import record_history
from tracemantle.parser import DocumentSettings, ParsedSkill, ParseError
from tracemantle.result import Diagnostic, Severity, ValidationResult
from tracemantle.sarif import format_sarif
from tracemantle.tokenizer import TokenizerError, tokenizer_provenance


def _print_report(
    args: argparse.Namespace,
    results: list[ValidationResult],
    *,
    critique_source: str | None,
    graph_source_json: dict[str, Any] | None,
    graph_source_text: str | None,
    documents: dict[Path, ParsedSkill],
    exit_code: int,
) -> None:
    """Print the report in the requested format (no-op under --quiet)."""
    if args.quiet:
        return
    # Compute description quality score breakdowns when relevant.
    score_breakdowns: dict[str, dict[str, int]] = {}
    score_reasons: dict[str, dict[str, str]] = {}
    has_quality_diag = any(
        d.rule == "description.quality-score"
        for r in results
        for d in r.diagnostics
    )
    if has_quality_diag:
        from tracemantle.rules.description import explain_components, scorable_description, score_description
        for r in results:
            if r.path not in documents or not any(d.rule == "description.quality-score" for d in r.diagnostics):
                continue
            desc = scorable_description(documents[r.path])
            if desc is not None:
                score_breakdowns[str(r.path)] = score_description(desc)[2]
                if args.explain_score:
                    score_reasons[str(r.path)] = explain_components(desc)

    if args.format == "json":
        try:
            provenance = tokenizer_provenance(args.tokenizer)
        except TokenizerError:
            provenance = {"backend": args.tokenizer, "status": "unavailable"}
        print(_format_json(
            results,
            __version__,
            critique_source=critique_source,
            graph_source=graph_source_json,
            score_breakdowns=score_breakdowns or None,
            gate_exit_code=exit_code,
            tokenizer=provenance,
        ))
    elif args.format == "md":
        print(_format_markdown(
            results,
            critique_source=critique_source,
            graph_source=graph_source_text,
        ))
    elif args.format == "agent":
        print(_format_agent(
            results,
            critique_source=critique_source,
            graph_source=graph_source_text,
        ))
    elif args.format == "github":
        print(_format_github(results))
    elif args.format == "sarif":
        print(format_sarif(results, __version__, gate_exit_code=exit_code))
    else:
        use_color = not args.no_color and sys.stdout.isatty()
        print(_format_text(
            results,
            color=use_color,
            critique_source=critique_source,
            graph_source=graph_source_text,
            score_breakdowns=score_breakdowns or None,
            score_reasons=score_reasons or None,
            explain_score=args.explain_score,
        ))


def run_validation(
    args: argparse.Namespace,
    paths: list[Path],
    agent_id: str,
    graph_agent_id: str,
) -> None:
    """Run symbolic validation, merge any ingested diagnostics, record history,
    print the report, and exit with the computed code."""
    # An ingested agent response describes exactly one skill, so it cannot be
    # fanned out across multiple resolved paths without stamping the first
    # skill's diagnostics onto every file. Reject the combination up front.
    if len(paths) > 1:
        active_ingest_flags = [
            flag
            for flag, value in (
                ("--ingest-critique", args.ingest_critique),
                ("--ingest-graph", args.ingest_graph),
            )
            if value is not None
        ]
        if active_ingest_flags:
            flags = " and ".join(active_ingest_flags)
            print(
                f"Error: {flags} applies one agent response to one skill, but "
                f"{len(paths)} SKILL.md paths were resolved. Run it once per skill, "
                f"pointing at a single SKILL.md.",
                file=sys.stderr,
            )
            sys.exit(2)

    documents: dict[Path, ParsedSkill] = {}
    results: list[ValidationResult] = []
    for path, skill in parse_batch(paths, getattr(args, 'document_settings', DocumentSettings())):
        if isinstance(skill, ParseError):
            results.append(ValidationResult(path, [Diagnostic('parse.error', Severity.ERROR, str(skill), line=skill.line)]))
            continue
        documents[path] = skill
        results.append(validate(skill, max_lines=args.max_lines, max_tokens=args.max_tokens,
            skip_dirname_check=args.skip_dirname_check, skip_ref_check=args.skip_ref_check,
            min_desc_score=args.min_desc_score, strict_vscode=args.strict_vscode,
            strict_cursor=args.strict_cursor, strict_all=args.strict_all, target_agent=args.target_agent))

    critique_source: str | None = None
    graph_source_text: str | None = None
    graph_source_json: dict[str, Any] | None = None

    if args.ingest_critique is not None:
        raw = read_ingest_raw(args.ingest_critique, 'critique response')

        try:
            first_skill = documents[paths[0]]
            critique_diags = ingest_critique_response(first_skill, raw)
        except (CritiqueParseError, KeyError) as exc:
            critique_diags = [
                Diagnostic(
                    rule="semantic.ingest.parse_error",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            ]

        results = [merge_diagnostics(r, critique_diags) for r in results]
        critique_source = agent_id

    if args.ingest_graph is not None:
        raw_graph = read_ingest_raw(args.ingest_graph, 'graph response')

        try:
            first_skill = documents[paths[0]]
            agent_graph = extract_graph_agent(first_skill, raw_graph)
            heuristic_graph = extract_graph_heuristic(first_skill)
            agent_graph_diags = run_graph_analyzers(agent_graph)
            divergence_diags = run_divergence_analyzers(agent_graph, heuristic_graph)
            all_graph_diags = agent_graph_diags + divergence_diags
            graph_source_text = f"agent ({graph_agent_id})"
            graph_source_json = {"mode": "agent", "agent": graph_agent_id}
        except (GraphParseError, GraphLimitError, KeyError) as exc:
            all_graph_diags = [
                Diagnostic(
                    rule="semantic.ingest.graph_parse_error",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            ]

        for i, result in enumerate(results):
            results[i] = merge_diagnostics(result, all_graph_diags)

    elif args.analyze_graph:
        for i, (path, result) in enumerate(zip(paths, results, strict=True)):
            graph_skill = documents.get(path)
            if graph_skill is None:
                continue
            try:
                graph = extract_graph_heuristic(graph_skill)
                graph_diags = run_graph_analyzers(graph)
            except GraphLimitError as exc:
                graph_diags = [Diagnostic('graph.limit', Severity.ERROR, str(exc))]
            results[i] = merge_diagnostics(result, graph_diags)
        graph_source_text = "heuristic"
        graph_source_json = {"mode": "heuristic"}

    results = filter_results(results, args.ignore_prefixes)
    if args.history:
        record_history(args, paths, results, agent_id, graph_agent_id, documents)
    final_exit_code = compute_exit_code(results, strict_all=args.strict_all)
    if args.fail_on_regression and any(d.rule == 'history.skill.regressed' for r in results for d in r.diagnostics):
        final_exit_code = 1

    _print_report(
        args,
        results,
        critique_source=critique_source,
        graph_source_json=graph_source_json,
        graph_source_text=graph_source_text,
        documents=documents,
        exit_code=final_exit_code,
    )

    sys.exit(final_exit_code)
