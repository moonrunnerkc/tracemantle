"""Per-skill validation history for the CLI: printing a ledger
(--show-history) and recording a run with regression checks (--history).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tracemantle import __version__
from tracemantle.core import (
    LedgerError,
    RunAgents,
    ValidationModes,
    build_entry,
    check_regression,
    ledger_path_for,
    load_ledger,
    merge_diagnostics,
    render_ledger_json,
    render_ledger_text,
)
from tracemantle.display import terminal
from tracemantle.gate import compute_exit_code, filter_results
from tracemantle.history_store import append_history, comparable_runs, history_identity
from tracemantle.parser import ParsedSkill
from tracemantle.result import Diagnostic, Severity, ValidationResult
from tracemantle.storage import EvidenceError


def run_show_history(args: argparse.Namespace, paths: list[Path]) -> None:
    """Print the validation history ledger for the first path and exit.

    Each skill has its own per-skill ledger, so multi-target invocations cannot
    map onto a single ledger render; the additional paths are ignored with a
    stderr warning so the silent skip is visible.
    """
    if len(paths) > 1:
        print(
            terminal(f"warning: --show-history reads one ledger; ignoring extra paths: "
            f"{', '.join(str(p) for p in paths[1:])}. "
            f"Run --show-history once per skill to read its ledger."),
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
            terminal(f"No history ledger found for {target_path}. "
            f"Run 'tracemantle {target_path} --history' to start tracking."),
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
        print(terminal(f"No history ledger found for {target_path}."), file=sys.stderr)
        sys.exit(2)
    if not args.quiet:
        if args.format == "json":
            print(render_ledger_json(ledger))
        else:
            print(render_ledger_text(ledger))
    sys.exit(0)


def record_history(
    args: argparse.Namespace,
    paths: list[Path],
    results: list[ValidationResult],
    agent_id: str,
    graph_agent_id: str,
    documents: dict[Path, ParsedSkill],
) -> None:
    """Append a ledger entry per target and merge any regression diagnostics.

    Mutates ``results`` in place (regression/write-failure diagnostics are
    appended per target, then ignore prefixes are reapplied). Each SKILL.md has
    its own per-skill ledger next to it, and each entry records that file's own
    exit code.
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
        # Regression detection compares validity and content only; the exit
        # code recorded here is the file's own, before any regression.
        preliminary_entry = build_entry(
            skill_for_history,
            results[index],
            modes,
            run_agents,
            compute_exit_code([results[index]], strict_all=args.strict_all),
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
        # A regression is a WARNING; --fail-on-regression escalates the
        # file's recorded code below and the batch gate in run_validation.
        if regression_diags:
            results[index] = merge_diagnostics(results[index], regression_diags)

        results[index] = filter_results([results[index]], args.ignore_prefixes)[0]
        file_exit_code = compute_exit_code([results[index]], strict_all=args.strict_all)
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
