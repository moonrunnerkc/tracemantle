"""Capture unscored compatibility probes against pinned public skill sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from verify_workflow_study import REVISION as TRACEMANTLE_REVISION
from verify_workflow_study import Command, run

UPSTREAM = "https://github.com/trailofbits/skills.git"
REVISION = "1f68e03536f7980d4c0e6869596f708043a19443"
SKILL = "plugins/static-analysis/skills/sarif-parsing"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New directory for checkout and logs")
    parser.add_argument("--python", required=True, type=Path, help="Python from verify_workflow_study's heuristic-venv")
    args = parser.parse_args()
    # Do not resolve the executable symlink: a venv's Python symlink points at the
    # system interpreter, and resolving it would discard the environment.
    python = str(args.python.absolute())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    logs = output / "logs"
    logs.mkdir()
    source = output / "skills"
    started = time.monotonic()
    observed = datetime.now(timezone.utc).isoformat()
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL") if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    commands: list[Command] = []

    def execute(name: str, argv: list[str], cwd: Path, required: bool = False) -> None:
        command = run(argv, cwd, logs / name, env, started + 900)
        commands.append(command)
        if required and command.exit_code:
            raise RuntimeError(f"Probe setup failed: {name}")

    try:
        execute("init", ["git", "init", "--quiet", str(source)], output, True)
        execute("fetch", ["git", "fetch", "--quiet", "--depth=1", UPSTREAM, REVISION], source, True)
        execute("checkout", ["git", "checkout", "--quiet", "--detach", REVISION], source, True)
        execute("environment", [python, "-m", "pip", "list", "--format=json"], source, True)
        execute("tool-version", [python, "-m", "tracemantle", "--version"], source, True)
        execute("jq-version", ["jq", "--version"], source, True)
        execute("upstream-metadata-self-test", [python, ".github/scripts/validate_plugin_metadata.py", "--self-test"], source)
        execute("upstream-metadata", [python, ".github/scripts/validate_plugin_metadata.py"], source)
        execute("upstream-interfaces", [python, ".github/scripts/validate_skill_interfaces.py"], source)
        execute("sarif-tests", [python, "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider", "--import-mode=importlib", ".",
                f"--junitxml={logs / 'sarif-tests.xml'}"], source / SKILL / "resources")
        execute("tracemantle-validation", [python, "-m", "tracemantle", f"{SKILL}/SKILL.md", "--format", "json"], source)
        execute("tracemantle-manifest", [python, "-m", "tracemantle", "manifest", SKILL, "--format", "json"], source)
        execute("source-status", ["git", "status", "--porcelain"], source)
    finally:
        report = {
            "schema_version": 1, "purpose": "exploratory public-source compatibility; not a deployment or scored evaluation",
            "repository": UPSTREAM, "revision": REVISION, "skill": SKILL,
            "tracemantle_revision": TRACEMANTLE_REVISION, "observed_at": observed,
            "platform": platform.platform(), "elapsed_seconds": time.monotonic() - started,
            "scored_cases": 0, "model_calls": 0, "model_tokens": 0, "model_cost_usd": 0,
            "commands": [asdict(command) for command in commands],
            "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(logs.iterdir())},
        }
        (output / "probe.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Probe records captured; exit codes in probe.json are findings, not a deployment verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
