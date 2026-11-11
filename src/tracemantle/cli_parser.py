"""Argument parser for the validation CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from tracemantle import __version__
from tracemantle.profile_freshness import DEFAULT_MAX_AGE_DAYS

_EPILOG = """\
examples:
  tracemantle SKILL.md                         validate one file
  tracemantle skills/ --strict --format github  fail CI on errors or warnings
  tracemantle SKILL.md --format json            preserve diagnostics as structured data

optional evidence commands (COMMAND --help for details):
  tracemantle manifest BUNDLE
  tracemantle import-evidence EXPORT --bundle BUNDLE --store STORE
  tracemantle compare BASELINE CANDIDATE --trusted-root REPO --base-revision SHA
  tracemantle migrate-history LEDGER --store STORE

Diagnostics name the file, line and rule. Specification errors need fixing;
heuristic advice and compatibility warnings are separate findings.
Guide: https://github.com/moonrunnerkc/tracemantle/blob/main/docs/getting-started.md
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the validation CLI parser. The evidence subcommands have their own
    parser in product_commands; generate_reference.py documents both."""
    parser = argparse.ArgumentParser(
        prog="tracemantle",
        allow_abbrev=False,
        usage="%(prog)s PATH [PATH ...] [options]",
        description="Check SKILL.md files locally: frontmatter, references, size and compatibility advice.\n"
                    "Start: tracemantle SKILL.md | Directory: tracemantle skills/\n"
                    "No account or evidence policy needed. A static pass does not prove live agent behavior.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    basic = parser.add_argument_group("everyday validation")
    settings = parser.add_argument_group("configuration and thresholds")
    compatibility = parser.add_argument_group("compatibility advice")
    advanced = parser.add_argument_group("optional analysis, prompts and history")
    parser.add_argument(
        "path",
        nargs="+",
        type=Path,
        help="Path to a SKILL.md file or a directory to scan recursively. Multiple paths accepted.",
    )
    settings.add_argument("--tokenizer", choices=["heuristic", "tiktoken"], default="heuristic", help="Token backend (default: heuristic; tiktoken may download on a cold cache).")
    basic.add_argument(
        "--format",
        choices=["text", "json", "md", "agent", "github", "sarif"],
        default="text",
        help="Output format (default: text). sarif writes a SARIF 2.1.0 log for code-scanning upload.",
    )
    settings.add_argument(
        "--max-lines",
        type=int,
        default=None,
        metavar="N",
        help="Override the line-count threshold (default: 500).",
    )
    settings.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        metavar="N",
        help="Override the token-count threshold (default: 8000).",
    )
    settings.add_argument(
        "--ignore",
        action="append",
        dest="ignore_prefixes",
        metavar="PREFIX",
        default=[],
        help="Suppress rules matching this prefix. Can be repeated.",
    )
    basic.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable colored output.",
    )
    basic.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=False,
        help="Suppress all output. Only the exit code indicates result.",
    )
    settings.add_argument(
        "--skip-dirname-check",
        action="store_true",
        default=False,
        help="Skip directory-name matching check (useful for CI temp paths).",
    )
    settings.add_argument(
        "--skip-ref-check",
        action="store_true",
        default=False,
        help="Skip file reference validation (useful when referenced files are unavailable).",
    )
    settings.add_argument(
        "--min-desc-score",
        type=int,
        default=None,
        metavar="N",
        help="Minimum description quality score (0-100). Below this triggers a warning.",
    )
    settings.add_argument(
        "--explain-score",
        action="store_true",
        default=False,
        help="Show per-dimension breakdown for description quality scores.",
    )
    compatibility.add_argument(
        "--target-agent",
        choices=["claude", "vscode", "cursor", "all"],
        default="all",
        help="Scope compatibility checks to a specific agent (default: all).",
    )
    compatibility.add_argument(
        "--strict-vscode",
        action="store_true",
        default=False,
        help="Promote VS Code compatibility issues to errors.",
    )
    compatibility.add_argument(
        "--strict-cursor",
        action="store_true",
        default=False,
        help="Promote Cursor compatibility issues to errors.",
    )
    basic.add_argument(
        "--strict",
        dest="strict_all",
        action="store_true",
        default=False,
        help=(
            "Strict mode. Escalates warning-only runs to exit 1, "
            "promotes VS Code compatibility to errors (same as --strict-vscode), "
            "promotes Cursor compatibility to errors (same as --strict-cursor), "
            "and enables the 'all' field in config for future strict rules."
        ),
    )
    basic.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    settings.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Explicit TOML config. Otherwise merge legacy and TraceMantle settings at the nearest project root.",
    )
    advanced.add_argument(
        "--semantic",
        action="store_true",
        default=False,
        help="Run semantic-adjacent validation. Implies --analyze-graph when --ingest-graph is not supplied.",
    )
    advanced.add_argument(
        "--agent-reason",
        action="store_true",
        default=False,
        help="Agent-native workflow shortcut. Without ingested responses, emits an agent prompt packet and exits 0.",
    )
    advanced.add_argument(
        "--emit-critique-prompt",
        action="store_true",
        default=False,
        help=(
            "Print the agent self-critique prompt to stdout and exit 0. "
            "Skips all symbolic validation. Use --format json to wrap in {\"prompt\": \"...\"}."
        ),
    )
    advanced.add_argument(
        "--ingest-critique",
        metavar="PATH",
        default=None,
        help=(
            "Read an agent self-critique JSON response from PATH (use - for stdin), "
            "convert to diagnostics, merge with symbolic results, and emit a unified report. "
            "Exit code 3 signals semantic drift when symbolic validation passed."
        ),
    )
    advanced.add_argument(
        "--critique-agent",
        choices=["claude", "codex", "cursor"],
        default=None,
        metavar="NAME",
        help=(
            "Agent variant for the self-critique prompt (claude, codex, cursor; default: claude). "
            "Requires --emit-critique-prompt or --ingest-critique."
        ),
    )
    advanced.add_argument(
        "--emit-graph",
        action="store_true",
        default=False,
        help=(
            "Print the extracted capability graph to stdout and exit 0. "
            "Replaces the validation report. Use --format json for machine-readable output."
        ),
    )
    advanced.add_argument(
        "--analyze-graph",
        action="store_true",
        default=False,
        help=(
            "Extract the capability graph, run graph analyzers, and merge diagnostics "
            "into the validation report. Augments (does not replace) the report."
        ),
    )
    advanced.add_argument(
        "--emit-graph-prompt",
        action="store_true",
        default=False,
        help=(
            "Print the graph-extraction prompt to stdout and exit 0. "
            "Hand the output to an agent, then use --ingest-graph with the response. "
            "Mutually exclusive with all other emit and augment modes."
        ),
    )
    advanced.add_argument(
        "--ingest-graph",
        metavar="PATH",
        default=None,
        help=(
            "Read an agent graph-extraction JSON response from PATH (use - for stdin), "
            "build a CapabilityGraph, run graph analyzers and divergence analyzers, and "
            "merge all diagnostics into the report. Compatible with --ingest-critique. "
            "Supersedes --analyze-graph (which does heuristic-only analysis)."
        ),
    )
    advanced.add_argument(
        "--graph-agent",
        choices=["claude", "codex", "cursor"],
        default=None,
        metavar="NAME",
        help=(
            "Agent variant for the graph-extraction prompt (claude, codex, cursor; default: claude). "
            "Requires --emit-graph-prompt or --ingest-graph."
        ),
    )
    advanced.add_argument(
        "--history",
        action="store_true",
        default=False,
        help=(
            "Write an immutable validation record outside the skill bundle, "
            "under its parent .tracemantle/history directory. Off by default. Incompatible with emit modes."
        ),
    )
    advanced.add_argument(
        "--show-history",
        action="store_true",
        default=False,
        help=(
            "Print the validation history ledger for the skill and exit 0. "
            "Skips all validation. Use --format json for machine-readable output. "
            "Incompatible with emit modes and with --history."
        ),
    )
    advanced.add_argument(
        "--fail-on-regression",
        action="store_true",
        default=False,
        help=(
            "Exit 1 when --history is active and a regression is detected "
            "(history.skill.regressed fires). Without this flag, regressions are "
            "warnings that do not affect the exit code. Independent of --strict."
        ),
    )
    advanced.add_argument(
        "--activation-hypotheses",
        action="store_true",
        default=False,
        help=(
            "Experimental emit mode. Generate likely natural-language activation triggers "
            "for the skill and exit 0."
        ),
    )
    compatibility.add_argument(
        "--check-profile-freshness",
        action="store_true",
        default=False,
        help=(
            "Warn on stderr when a verified-profile entry is older than --profile-max-age-days or its docs page "
            "reports a later Last-Modified. Sends one HTTP HEAD per checked profile. Never changes the exit code."
        ),
    )
    compatibility.add_argument(
        "--profile-max-age-days",
        type=int,
        default=None,
        metavar="N",
        help=f"Age limit for --check-profile-freshness (default: {DEFAULT_MAX_AGE_DAYS}).",
    )
    compatibility.add_argument(
        "--profile-registry",
        type=Path,
        default=None,
        metavar="PATH",
        help="Verified-profile TOML for --check-profile-freshness (default: the registry shipped with the package).",
    )
    return parser
