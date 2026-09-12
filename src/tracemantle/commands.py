"""Command execution for the tracemantle CLI.

`cli.py` owns argument wiring (parser construction, config application, dispatch).
This module owns what each mode does: collecting paths, reading ingest payloads,
emitting prompts and graphs, printing the history ledger, and running the default
validation pipeline. The functions here carry their own exit codes via
`sys.exit`, matching the behavior they had when they lived in `cli.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from tracemantle import __version__
from tracemantle.agents import get_graph_prompt
from tracemantle.agents._ingest import MAX_INGEST_BYTES
from tracemantle.agents.graph_parser import GraphParseError
from tracemantle.agents.parser import CritiqueParseError
from tracemantle.config_loader import project_configs
from tracemantle.core import (
    LedgerError,
    RunAgents,
    ValidationModes,
    build_entry,
    check_regression,
    extract_graph_agent,
    extract_graph_heuristic,
    generate_activation_hypotheses,
    ingest_critique_response,
    ledger_path_for,
    load_ledger,
    merge_diagnostics,
    render_activation_json,
    render_activation_markdown,
    render_activation_text,
    render_critique_prompt,
    render_graph_json,
    render_graph_text,
    render_ledger_json,
    render_ledger_text,
    run_divergence_analyzers,
    run_graph_analyzers,
    validate,
)
from tracemantle.core.graph import GraphLimitError
from tracemantle.display import terminal
from tracemantle.formatters import (
    _format_agent,
    _format_github,
    _format_json,
    _format_markdown,
    _format_text,
)
from tracemantle.history_store import append_history, comparable_runs, history_identity
from tracemantle.io_limits import (
    MAX_SCAN_BYTES,
    MAX_SCAN_FILES,
    UntrustedInputError,
    display_path,
    read_guarded_text,
    reject_control_characters,
)
from tracemantle.parser import DocumentSettings, ParsedSkill, ParseError
from tracemantle.parser import parse as _parse_skill
from tracemantle.result import Diagnostic, Severity, ValidationResult
from tracemantle.storage import EvidenceError
from tracemantle.tokenizer import TokenizerError, tokenizer_provenance

# Delimiter used between prompts when emitting for multiple skills.
_PROMPT_DELIMITER = "# === tracemantle:critique-prompt:{path} ==="

# Delimiter used between graph renders when emitting for multiple skills.
_GRAPH_DELIMITER = "# === tracemantle:graph:{path} ==="

# Delimiter used between graph-extraction prompts when emitting for multiple skills.
_GRAPH_PROMPT_DELIMITER = "# === tracemantle:graph-prompt:{path} ==="


# ---------------------------------------------------------------------------
# Path collection
# ---------------------------------------------------------------------------


def collect_paths(target: Path) -> list[Path]:
    """Return a list of SKILL.md files to validate.

    For a directory, recursively finds all files named exactly 'SKILL.md'.
    For a file, returns it directly without name filtering.

    Uses ``os.walk(followlinks=False)`` so directory symlinks are not traversed:
    a symlink into another tree cannot pull in foreign files, and a symlink cycle
    cannot hang the scan. ``Path.rglob`` follows directory symlinks on some Python
    versions, which this avoids.
    """
    if not target.is_dir():
        return [target]
    found: list[Path] = []
    def walk_error(exc: OSError) -> None:
        raise UntrustedInputError(f"Cannot scan {target}: {exc}") from exc

    for dirpath, dirnames, filenames in os.walk(target, followlinks=False, onerror=walk_error):
        dirnames[:] = sorted(d for d in dirnames if d not in {'.git', '.venv', '__pycache__', '.tracemantle'})
        if len(found) >= MAX_SCAN_FILES:
            raise UntrustedInputError(f"Scan exceeds the {MAX_SCAN_FILES}-file limit; split the batch.")
        if "SKILL.md" in filenames:
            found.append(Path(dirpath) / "SKILL.md")
    return sorted(found)


def resolve_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve the target paths to a list of SKILL.md files, exiting on error."""
    all_paths: list[Path] = []
    for target in args.path:
        if not target.exists():
            print(terminal(f"Error: path not found: {target}"), file=sys.stderr)
            sys.exit(2)
        try:
            paths = collect_paths(target)
        except (OSError, RuntimeError, UntrustedInputError) as exc:
            print(terminal(f"Error: {exc}"), file=sys.stderr)
            sys.exit(2)
        if not paths:
            print(terminal(f"No SKILL.md files found under: {target}"), file=sys.stderr)
            sys.exit(2)
        all_paths.extend(paths)
    try:
        unique = {p.resolve(): p for p in sorted(all_paths)}
        paths = [unique[key] for key in sorted(unique)]
        if len(paths) > MAX_SCAN_FILES:
            raise UntrustedInputError(f"Scan exceeds the {MAX_SCAN_FILES}-file limit.")
        if not args.config and any(project_configs(p) != args.config_paths for p in paths):
            raise UntrustedInputError("Mixed project roots are ambiguous. Validate each project separately or supply --config.")
        return paths
    except (OSError, RuntimeError, UntrustedInputError) as exc:
        print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(2)


def read_ingest_raw(ingest_path: str) -> str:
    """Read the raw critique response from PATH or stdin, exiting on error.

    Rejects payloads over ``MAX_INGEST_BYTES`` (exit 2). The stdin read is
    bounded so a runaway pipe cannot exhaust memory before the check fires.
    """
    if ingest_path == "-":
        payload = sys.stdin.buffer.read(MAX_INGEST_BYTES + 1)
        size = len(payload)
        try:
            raw = payload.decode('utf-8')
        except UnicodeDecodeError:
            print('Error: ingest stdin must contain UTF-8 text.', file=sys.stderr)
            sys.exit(2)
        if size > MAX_INGEST_BYTES:
            print(
                f"Error: ingest payload from stdin exceeds the {MAX_INGEST_BYTES}-byte cap. "
                f"Trim the response or split the run into smaller batches.",
                file=sys.stderr,
            )
            sys.exit(2)
        # stdin arrives already decoded, so only the control-character half of
        # the policy applies. A pipe carrying NULs is a binary stream, not JSON.
        try:
            reject_control_characters(raw, what="Ingest payload", source="stdin")
        except UntrustedInputError as exc:
            print(terminal(f"Error: {exc}"), file=sys.stderr)
            sys.exit(2)
        return raw
    p = Path(ingest_path)
    if not p.exists():
        # Echoed verbatim, not through display_path. This is the string the user
        # typed on the command line, so shortening it hides which path they got
        # wrong. display_path exists to keep discovered content from publishing
        # the host layout, which does not apply to the user's own argument.
        print(terminal(f"Error: critique response file not found: {p}"), file=sys.stderr)
        sys.exit(2)
    try:
        return read_guarded_text(p, max_bytes=MAX_INGEST_BYTES, what="Ingest response")
    except UntrustedInputError as exc:
        print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"Error: cannot read {display_path(p)}: {exc}", file=sys.stderr)
        sys.exit(2)


def _parse_or_exit(path: Path) -> ParsedSkill:
    """Parse a skill for an emit or history mode, or exit cleanly on failure.

    Plain validation renders an unparseable file (non-UTF-8, non-mapping
    frontmatter) as a clean ``parse.error`` diagnostic. The emit and history
    modes bypass that pipeline, so they mirror the behavior here: print the
    ParseError message to stderr and exit 1 instead of surfacing a traceback.
    """
    try:
        return _parse_skill(path)
    except ParseError as exc:
        print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Emit modes
# ---------------------------------------------------------------------------


def _emit_documents(paths: list[Path], fmt: str, mode: str, agent_id: str = "claude") -> None:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            skill = _parse_skill(path)
        except ParseError as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        if mode == 'graph':
            try:
                graph = extract_graph_heuristic(skill)
            except GraphLimitError as exc:
                errors.append({"path": str(path), "error": str(exc)})
                continue
            item = json.loads(render_graph_json(graph))
            rendered = render_graph_text(graph)
        else:
            prompt = render_critique_prompt(skill, agent_id=agent_id) if mode == 'critique' else get_graph_prompt(agent_id).render(skill)
            item = {"prompt": prompt}
            rendered = prompt
        items.append({"path": str(path), **item})
        if fmt != 'json':
            if len(paths) > 1:
                print(terminal(f"# === tracemantle:{'critique-prompt' if mode == 'critique' else mode}:{path} ==="))
            # Preserve generated layout while making all other controls inert.
            print("\n".join(terminal(line) for line in rendered.split('\n')))
    if fmt == 'json':
        payload: dict[str, Any] = {"tool": "TraceMantle", "version": __version__, "schema_version": 2, "mode": mode}
        if len(items) == 1 and len(paths) == 1:
            payload.update(items[0])
        else:
            payload['results'] = items
        if errors:
            payload['errors'] = errors
        print(json.dumps(payload, indent=2))
    else:
        for error in errors:
            print(terminal(f"Error: {error['path']}: {error['error']}"), file=sys.stderr)
    if errors:
        sys.exit(1)


def emit_graph(paths: list[Path], fmt: str) -> None:
    _emit_documents(paths, fmt, 'graph')


def emit_critique_prompts(paths: list[Path], fmt: str, agent_id: str = 'claude') -> None:
    _emit_documents(paths, fmt, 'critique', agent_id)


def emit_graph_prompts(paths: list[Path], fmt: str, agent_id: str = 'claude') -> None:
    _emit_documents(paths, fmt, 'graph-prompt', agent_id)


def emit_agent_reason_packet(paths: list[Path], fmt: str, critique_agent: str, graph_agent: str) -> None:
    """Print a combined critique and graph prompt packet for in-agent execution."""
    packets: list[dict[str, str]] = []
    errors = []
    for path in paths:
        try:
            skill = _parse_skill(path)
        except ParseError as exc:
            errors.append({'path': str(path), 'error': str(exc)})
            continue
        packets.append({
            "path": str(path),
            "critique_prompt": render_critique_prompt(skill, agent_id=critique_agent),
            "graph_prompt": get_graph_prompt(graph_agent).render(skill),
        })

    if fmt == "json":
        print(json.dumps({'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2, "agent_reason": packets, 'errors': errors}, indent=2))
        if errors:
            sys.exit(1)
        return

    for error in errors:
        print(terminal(f"Error: {error['path']}: {error['error']}"), file=sys.stderr)
    for index, raw_packet in enumerate(packets, start=1):
        packet = {key: '\n'.join(terminal(line) for line in value.split('\n')) if key.endswith('_prompt') else terminal(value) for key, value in raw_packet.items()}
        if len(packets) > 1:
            print(f"# === tracemantle:agent-reason:{packet['path']} ===")
        if fmt == "md":
            print(f"# Agent Reason Packet {index}\n")
            print(f"Path: `{packet['path']}`\n")
            print("## Critique prompt\n")
            print(f"```text\n{packet['critique_prompt']}\n```\n")
            print("## Graph prompt\n")
            print(f"```text\n{packet['graph_prompt']}\n```")
        elif fmt == "agent":
            print("tracemantle agent-reason packet")
            print(f"path: {packet['path']}")
            print("task: run both prompts, save each JSON response, then invoke tracemantle with --ingest-critique and --ingest-graph")
            print("critique_prompt:")
            print(packet["critique_prompt"])
            print("graph_prompt:")
            print(packet["graph_prompt"])
        else:
            print("Critique prompt:")
            print(packet["critique_prompt"])
            print("\nGraph prompt:")
            print(packet["graph_prompt"])

    if errors:
        sys.exit(1)


def emit_activation(paths: list[Path], fmt: str) -> None:
    """Print activation hypotheses for each path and exit 0."""
    multiple = len(paths) > 1
    reports = []
    errors = []
    for path in paths:
        try:
            reports.append((path, generate_activation_hypotheses(_parse_skill(path))))
        except ParseError as exc:
            errors.append({'path': str(path), 'error': str(exc)})
    if fmt == 'json':
        payload: dict[str, Any] = {'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2}
        if multiple or not reports:
            payload['activation_reports'] = [json.loads(render_activation_json(report)) for _, report in reports]
        else:
            payload.update(json.loads(render_activation_json(reports[0][1])))
        if errors:
            payload['errors'] = errors
        print(json.dumps(payload, indent=2))
    else:
        for path, report in reports:
            if multiple:
                print(terminal(f'# === tracemantle:activation:{path} ==='))
            print(render_activation_markdown(report) if fmt == 'md' else render_activation_text(report))
        for error in errors:
            print(terminal(f"Error: {error['path']}: {error['error']}"), file=sys.stderr)
    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def run_show_history(args: argparse.Namespace, paths: list[Path]) -> None:
    """Print the validation history ledger for the first path and exit.

    Each skill has its own per-skill ledger, so multi-target invocations cannot
    map onto a single ledger render; the additional paths are ignored with a
    stderr warning so the silent skip is visible.
    """
    if len(paths) > 1:
        print(
            f"warning: --show-history reads one ledger; ignoring extra paths: "
            f"{', '.join(str(p) for p in paths[1:])}. "
            f"Run --show-history once per skill to read its ledger.",
            file=sys.stderr,
        )
    target_path = paths[0]
    lp = ledger_path_for(target_path)
    if not lp.exists():
        legacy = target_path.parent / '.skillcheck-history.json'
        if legacy.exists():
            lp = legacy
            print('Reading legacy history; use tracemantle migrate-history to copy it explicitly.', file=sys.stderr)
    if not lp.exists():
        print(
            f"No history ledger found for {target_path}. "
            f"Run 'tracemantle {target_path} --history' to start tracking.",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        ledger = load_ledger(lp)
    except (LedgerError, EvidenceError, OSError) as exc:
        # Exit 2: README documents it as the code for malformed input, and an
        # unreadable ledger is exactly that. This path returned 1 before, which
        # contradicted the documented contract.
        print(terminal(f"Error: {exc}"), file=sys.stderr)
        sys.exit(2)
    if ledger is None:
        print(f"No history ledger found for {target_path}.", file=sys.stderr)
        sys.exit(2)
    if not args.quiet:
        if args.format == "json":
            print(render_ledger_json(ledger))
        else:
            print(render_ledger_text(ledger))
    sys.exit(0)


# ---------------------------------------------------------------------------
# Default validation pipeline
# ---------------------------------------------------------------------------


def _compute_exit_code(
    results: list[ValidationResult],
    *,
    symbolic_errors_before_ingest: bool,
    any_ingest_failed: bool,
    strict_all: bool,
) -> int:
    """Return the process exit code from the merged results.

    Priority: symbolic/ingest failure (1) beats a semantic-only contradiction (3);
    a remaining error (e.g. an agent-graph contradiction) is 1; a warning-only run
    is 0 unless ``--strict`` escalates it to 1; otherwise 0.
    """
    if symbolic_errors_before_ingest or any_ingest_failed or any(d.severity == Severity.ERROR and (not d.rule.startswith("semantic.") or d.rule.startswith("semantic.ingest.")) for r in results for d in r.diagnostics):
        return 1
    if any(
        d.severity == Severity.ERROR
        for r in results
        for d in r.diagnostics
        if d.rule.startswith("semantic.")
    ):
        # Symbolic passed, all parses succeeded, but a critique ingest added a
        # semantic-namespace contradiction (semantic.*).
        return 3
    if any(not r.valid for r in results):
        # Any remaining errors (e.g. graph.contradiction from agent ingest).
        return 1
    if any(d.severity == Severity.WARNING for r in results for d in r.diagnostics):
        # Warning-only runs are a clean pass by default; --strict escalates
        # them to exit 1. Exit 2 stays reserved for tool-misuse / input errors.
        return 1 if strict_all else 0
    return 0


def _record_history(
    args: argparse.Namespace,
    paths: list[Path],
    results: list[ValidationResult],
    agent_id: str,
    graph_agent_id: str,
    final_exit_code: int,
    documents: dict[Path, ParsedSkill],
) -> int:
    """Append a ledger entry per target and merge any regression diagnostics.

    Mutates ``results`` in place (regression/write-failure diagnostics are
    appended per target). Each SKILL.md has its own per-skill ledger next to it.
    Returns the exit code, escalated to 1 the first time a target regresses when
    ``--fail-on-regression`` is set.
    """
    modes = ValidationModes(
        symbolic=True,
        critique=args.ingest_critique is not None,
        graph=args.ingest_graph is not None or args.analyze_graph,
    )
    run_agents = RunAgents(
        critique_agent=agent_id if args.ingest_critique is not None else None,
        graph_agent=graph_agent_id if args.ingest_graph is not None else None,
    )
    for index, path in enumerate(paths):
        identity: tuple[str, str] | None = None
        skill_for_history = documents.get(path)
        if skill_for_history is None:
            continue
        preliminary_entry = build_entry(
            skill_for_history,
            results[index],
            modes,
            run_agents,
            final_exit_code,
            __version__,
        )
        lp = ledger_path_for(path)
        try:
            identity = history_identity(skill_for_history, {name: getattr(args, name) for name in ('max_lines', 'max_tokens', 'min_desc_score', 'ignore_prefixes', 'skip_ref_check', 'skip_dirname_check', 'strict_all', 'strict_vscode', 'strict_cursor', 'target_agent', 'analyze_graph', 'semantic', 'critique_agent', 'graph_agent')})
            prior_runs = comparable_runs(lp, identity)
            regression_diags = check_regression(prior_runs, preliminary_entry)
        except (LedgerError, EvidenceError, OSError) as exc:
            regression_diags = [
                Diagnostic(
                    rule="history.read.failed",
                    severity=Severity.ERROR,
                    message=f"Could not read history ledger: {exc}",
                )
            ]
        if regression_diags:
            results[index] = merge_diagnostics(results[index], regression_diags)
            # Regression is WARNING by default; does not change the exit code.
            # --fail-on-regression promotes it to exit 1 the first time any
            # target regresses, and that escalated code is what subsequent
            # ledger entries (and the global exit) record.
            if args.fail_on_regression and any(
                d.rule == "history.skill.regressed" for d in regression_diags
            ):
                final_exit_code = 1

        results[index] = _filter_results([results[index]], args.ignore_prefixes)[0]
        file_exit_code = _compute_exit_code([results[index]], symbolic_errors_before_ingest=False, any_ingest_failed=False, strict_all=args.strict_all)
        if args.fail_on_regression and any(d.rule == 'history.skill.regressed' for d in results[index].diagnostics):
            file_exit_code = 1
        # Record this file's policy result, independently of the batch gate.
        final_entry = build_entry(
            skill_for_history,
            results[index],
            modes,
            run_agents,
            file_exit_code,
            __version__,
        )
        try:
            if identity is not None:
                append_history(lp, skill_for_history, final_entry, identity)
        except (LedgerError, EvidenceError, OSError) as exc:
            results[index] = merge_diagnostics(results[index], [
                Diagnostic(
                    rule="history.write.failed",
                    severity=Severity.WARNING,
                    message=f"Could not write history ledger to {lp}: {exc}",
                )
            ])
            # Write failure is a warning; validation exit code stands.
    return final_exit_code


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
        from tracemantle.rules.description import explain_components as _explain
        from tracemantle.rules.description import score_description as _score
        from tracemantle.template_detection import is_template
        for r in results:
            for d in r.diagnostics:
                if d.rule == "description.quality-score":
                    try:
                        skill = documents[r.path]
                        desc = skill.frontmatter.get("description")
                        if desc and isinstance(desc, str) and desc.strip() and not is_template(skill):
                            _, _, bd = _score(desc)
                            score_breakdowns[str(r.path)] = bd
                            if args.explain_score:
                                score_reasons[str(r.path)] = _explain(desc)
                    except KeyError:
                        continue
                    break  # one description per file

    if args.quiet:
        return

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
    scanned = 0
    for path in paths:
        try:
            if scanned >= MAX_SCAN_BYTES:
                raise ParseError(f"Scan exceeds the {MAX_SCAN_BYTES}-byte budget. Split the batch.")
            skill = _parse_skill(path, settings=getattr(args, 'document_settings', DocumentSettings()), max_bytes=MAX_SCAN_BYTES - scanned)
            scanned += len(skill.raw_text.encode('utf-8'))
            documents[path] = skill
            results.append(validate(skill, max_lines=args.max_lines, max_tokens=args.max_tokens,
                skip_dirname_check=args.skip_dirname_check, skip_ref_check=args.skip_ref_check,
                min_desc_score=args.min_desc_score, strict_vscode=args.strict_vscode,
                strict_cursor=args.strict_cursor, strict_all=args.strict_all, target_agent=args.target_agent))
        except ParseError as exc:
            results.append(ValidationResult(path, [Diagnostic('parse.error', Severity.ERROR, str(exc), line=exc.line)]))

    critique_source: str | None = None
    graph_source_text: str | None = None
    graph_source_json: dict[str, Any] | None = None

    if args.ingest_critique is not None:
        raw = read_ingest_raw(args.ingest_critique)

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
        raw_graph = read_ingest_raw(args.ingest_graph)

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

    results = _filter_results(results, args.ignore_prefixes)
    final_exit_code = _compute_exit_code(results, symbolic_errors_before_ingest=False,
        any_ingest_failed=False, strict_all=args.strict_all)
    if args.history:
        _record_history(args, paths, results, agent_id, graph_agent_id, final_exit_code, documents)
        results = _filter_results(results, args.ignore_prefixes)
        final_exit_code = _compute_exit_code(results, symbolic_errors_before_ingest=False,
            any_ingest_failed=False, strict_all=args.strict_all)
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


def _filter_results(results: list[ValidationResult], prefixes: list[str]) -> list[ValidationResult]:
    return [replace(r, diagnostics=[d for d in r.diagnostics if not any(d.rule.startswith(prefix) for prefix in prefixes)]) for r in results]
