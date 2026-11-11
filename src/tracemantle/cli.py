from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from tracemantle import __version__
from tracemantle.cli_inputs import resolve_paths
from tracemantle.cli_parser import build_parser
from tracemantle.commands import run_validation
from tracemantle.config import DEFAULT_RESERVED_WORDS
from tracemantle.config_loader import ConfigError, load_project_config
from tracemantle.display import terminal
from tracemantle.emit_modes import (
    emit_activation,
    emit_agent_reason_packet,
    emit_critique_prompts,
    emit_graph,
    emit_graph_prompts,
)
from tracemantle.history_commands import run_show_history
from tracemantle.modes import find_mode_conflict
from tracemantle.parser import DocumentSettings
from tracemantle.profile_freshness import DEFAULT_MAX_AGE_DAYS, SHIPPED_REGISTRY, freshness_warnings, load_verified_profiles


def _warn_on_stale_profiles(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.check_profile_freshness:
        if args.profile_max_age_days is not None or args.profile_registry is not None:
            parser.error("--profile-max-age-days and --profile-registry require --check-profile-freshness")
        return
    max_age_days = DEFAULT_MAX_AGE_DAYS if args.profile_max_age_days is None else args.profile_max_age_days
    if max_age_days < 1:
        parser.error("--profile-max-age-days must be at least 1")
    try:
        profiles = load_verified_profiles(args.profile_registry or SHIPPED_REGISTRY)
    except ConfigError as exc:
        parser.error(terminal(str(exc)))
    if args.target_agent != "all":
        profiles = tuple(profile for profile in profiles if profile.agent == args.target_agent)
    for warning in freshness_warnings(profiles, max_age_days=max_age_days, today=datetime.now(timezone.utc).date()):
        print(terminal(f"warning: {warning}"), file=sys.stderr)


# ---------------------------------------------------------------------------
# Config application
# ---------------------------------------------------------------------------


def _apply_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Apply immutable project settings unless a CLI field was explicitly supplied."""
    try:
        loaded, paths, legacy = load_project_config(args.path[0], args.config)
        for target in args.path[1:]:
            other, other_paths, _ = load_project_config(target, args.config)
            if other_paths != paths:
                raise ConfigError("Mixed project roots are ambiguous. Validate each project separately or supply --config.")
    except (ConfigError, OSError, RuntimeError) as exc:
        if args.format == 'json':
            print(json.dumps({'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2,
                              'gate': {'passed': False, 'exit_code': 2}, 'results': [],
                              'errors': [{'error': str(exc)}]}))
            sys.exit(2)
        parser.error(terminal(str(exc)))
    for path in paths:
        print(terminal(f"Loaded config from {path}"), file=sys.stderr)
    if legacy:
        print("Deprecated SkillCheck configuration: migrate to [tool.tracemantle] or tracemantle.toml.", file=sys.stderr)
    args.config_paths = paths
    explicit: frozenset[str] = getattr(args, "explicit_fields", frozenset())
    for name in loaded.supplied - {"extension_fields", "reserved_words"}:
        dest = "ignore_prefixes" if name == "ignore" else name
        if dest not in explicit:
            setattr(args, dest, getattr(loaded, name))
    args.document_settings = DocumentSettings(loaded.extension_fields, loaded.reserved_words or DEFAULT_RESERVED_WORDS, args.tokenizer)


# ---------------------------------------------------------------------------
# Mode conflict resolution
#
# The flags, their groups, and every incompatibility live in tracemantle.modes.
# This function only turns a detected conflict into stderr plus exit 2.
# ---------------------------------------------------------------------------


def _die_on_mode_conflict(args: argparse.Namespace) -> None:
    """Exit 2 with a diagnostic if the requested modes cannot run together."""
    message = find_mode_conflict(args)
    if message is not None:
        print(message, file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # Ensure UTF-8 output on Windows where the default encoding may be cp1252.
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") != "utf8":
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    if len(sys.argv) > 1 and sys.argv[1] in {"manifest", "import-evidence", "compare", "migrate-history"}:
        from tracemantle.product_commands import main as product_main
        product_main(sys.argv[1:])
        return
    parser = build_parser()
    args = parser.parse_args()
    option_dest = {option: action.dest for action in parser._actions for option in action.option_strings}
    args.explicit_fields = frozenset(option_dest[token.split("=", 1)[0]] for token in sys.argv[1:] if token.split("=", 1)[0] in option_dest)
    _apply_config(args, parser)

    # --strict: enable all strict modes.
    if args.strict_all:
        args.strict_vscode = True
        args.strict_cursor = True

    if args.format not in {"text", "json", "md", "agent", "github", "sarif"}:
        parser.error("format must be one of: text, json, md, agent, github, sarif")
    if args.target_agent not in {"claude", "vscode", "cursor", "all"}:
        parser.error("target-agent must be one of: claude, vscode, cursor, all")
    if args.critique_agent is not None and args.critique_agent not in {"claude", "codex", "cursor"}:
        parser.error("critique-agent must be one of: claude, codex, cursor")
    if args.graph_agent is not None and args.graph_agent not in {"claude", "codex", "cursor"}:
        parser.error("graph-agent must be one of: claude, codex, cursor")

    if args.semantic and args.ingest_graph is None:
        args.analyze_graph = True

    _die_on_mode_conflict(args)
    _warn_on_stale_profiles(args, parser)

    agent_id = args.critique_agent or "claude"
    graph_agent_id = args.graph_agent or "claude"

    # A project config may name an agent as a default for the modes that use
    # one; only an explicit flag without such a mode is a usage error.
    if "critique_agent" in args.explicit_fields and not args.emit_critique_prompt and not args.agent_reason and args.ingest_critique is None:
        parser.error("--critique-agent requires --emit-critique-prompt or --ingest-critique")

    if "graph_agent" in args.explicit_fields and not args.emit_graph_prompt and not args.agent_reason and args.ingest_graph is None:
        parser.error("--graph-agent requires --emit-graph-prompt or --ingest-graph")

    paths = resolve_paths(args)

    # --show-history: read the ledger for the first path, print it, and exit.
    if args.show_history:
        run_show_history(args, paths)

    # --emit-graph: emit the heuristic graph and skip symbolic validation entirely
    if args.emit_graph:
        emit_graph(paths, fmt=args.format)
        sys.exit(0)

    # --emit-critique-prompt: skip symbolic validation entirely
    if args.emit_critique_prompt:
        emit_critique_prompts(paths, fmt=args.format, agent_id=agent_id)
        sys.exit(0)

    # --emit-graph-prompt: render and print the graph-extraction prompt, then exit
    if args.emit_graph_prompt:
        emit_graph_prompts(paths, fmt=args.format, agent_id=graph_agent_id)
        sys.exit(0)

    if args.agent_reason and args.ingest_critique is None and args.ingest_graph is None:
        emit_agent_reason_packet(paths, args.format, agent_id, graph_agent_id)
        sys.exit(0)

    if args.activation_hypotheses:
        emit_activation(paths, args.format)
        sys.exit(0)

    run_validation(args, paths, agent_id, graph_agent_id)
