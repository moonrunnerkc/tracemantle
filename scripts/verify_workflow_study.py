"""Reproduce preparation checks on pinned source, without running an agent."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REVISION = "721845b35ef450ebaaf4c7bfb20990db92d0ed3c"
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Command:
    argv: list[str]
    cwd: str
    exit_code: int
    elapsed_seconds: float
    timed_out: bool
    stdout: str
    stderr: str
    stdout_sha256: str
    stderr_sha256: str


def run(argv: list[str], cwd: Path, output: Path, env: dict[str, str], deadline: float) -> Command:
    started = time.monotonic()
    remaining = min(900, deadline - started)
    if remaining <= 0:
        raise TimeoutError("Preparation exceeded the one-hour local resource cap")
    stdout = output.with_suffix(".stdout.txt")
    stderr = output.with_suffix(".stderr.txt")
    timed_out = False
    with stdout.open("wb") as out, stderr.open("wb") as err:
        with subprocess.Popen(argv, cwd=cwd, env=env, stdout=out, stderr=err, start_new_session=True) as proc:
            try:
                code = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                code = proc.wait()
    result = Command(argv, str(cwd), code, time.monotonic() - started, timed_out,
                     stdout.name, stderr.name, hashlib.sha256(stdout.read_bytes()).hexdigest(),
                     hashlib.sha256(stderr.read_bytes()).hexdigest())
    print(f"{output.name}: exit {code}, {result.elapsed_seconds:.3f}s", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New external directory for environments and logs")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform != "linux":
        parser.error("This preparation run is pinned to CPython 3.12 on Linux")
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("Output must be outside the source repository")
    output.mkdir(parents=True, exist_ok=False)
    logs = output / "logs"
    logs.mkdir()
    started = time.monotonic()
    observed = datetime.now(timezone.utc).isoformat()
    commands: list[Command] = []
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL") if key in os.environ}
    env.update(PIP_DISABLE_PIP_VERSION_CHECK="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
               GIT_AUTHOR_NAME="moonrunnerkc", GIT_COMMITTER_NAME="moonrunnerkc",
               GIT_AUTHOR_EMAIL="study@example.invalid", GIT_COMMITTER_EMAIL="study@example.invalid")

    def execute(name: str, argv: list[str], cwd: Path, required: bool = False) -> None:
        result = run(argv, cwd, logs / name, env, started + 3600)
        commands.append(result)
        if required and result.exit_code:
            raise RuntimeError(f"Required setup command failed: {name}; see {logs}")

    try:
        for variant in ("heuristic", "tiktoken"):
            checkout = output / variant
            execute(f"{variant}-clone", ["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(ROOT), str(checkout)], ROOT, True)
            execute(f"{variant}-checkout", ["git", "checkout", "--detach", REVISION], checkout, True)
            venv = output / f"{variant}-venv"
            execute(f"{variant}-venv", [sys.executable, "-m", "venv", str(venv)], output, True)
            python = str(venv / "bin/python")
            env["PATH"] = str(venv / "bin") + os.pathsep + os.environ["PATH"]
            for key in ("XDG_CACHE_HOME", "PRE_COMMIT_HOME", "TIKTOKEN_CACHE_DIR", "TMPDIR"):
                directory = output / f"{variant}-{key.lower()}"
                directory.mkdir()
                env[key] = str(directory)
            extra = ".[dev]" if variant == "heuristic" else ".[dev,tiktoken]"
            execute(f"{variant}-install", [python, "-m", "pip", "install", "--no-cache-dir", "-c", "constraints-dev.txt", "-e", extra], checkout, True)
            execute(f"{variant}-dependencies", [python, "-m", "pip", "list", "--format=json"], checkout)
            execute(f"{variant}-pip-check", [python, "-m", "pip", "check"], checkout)
            execute(f"{variant}-tokenizer-presence", [python, "-c",
                    "import importlib.util; present = importlib.util.find_spec('tiktoken') is not None; "
                    f"print('tiktoken present:', present); assert present is {variant == 'tiktoken'}"], checkout, True)
            execute(f"{variant}-tests", [python, "-m", "pytest", "tests/", "-q", "-ra", "-p", "no:cacheprovider",
                    "--cov-fail-under=80", f"--junitxml={logs / (variant + '-tests.xml')}"], checkout)
            if variant == "heuristic":
                execute("ruff", [str(venv / "bin/ruff"), "check", "src", "tests", "scripts"], checkout)
                execute("mypy", [str(venv / "bin/mypy")], checkout)
                execute("reference", [python, "scripts/generate_reference.py", "--check"], checkout)
                execute("version", [python, "-m", "tracemantle", "--version"], checkout)
                execute("self-host-validation", [python, "-m", "tracemantle", "skills/tracemantle/SKILL.md", "--format", "json"], checkout)
                execute("self-host-manifest", [python, "-m", "tracemantle", "manifest", "skills/tracemantle", "--format", "json"], checkout)
            else:
                execute("calibration", [python, "scripts/calibrate_advisories.py", "--output", str(logs / "calibration.json")], checkout)
                execute("conformance-install", [python, "-m", "pip", "install", "--no-cache-dir", "-c", "constraints-dev.txt", "strictyaml", "click"], checkout, True)
                execute("conformance", [python, "scripts/verify_reference_corpus.py", "--output", str(logs / "conformance.json")], checkout)
    finally:
        report = {
            "schema_version": 1, "purpose": "preparation, not a consumer deployment or scored study",
            "source_revision": REVISION, "observed_at": observed, "python": sys.version,
            "platform": platform.platform(), "elapsed_seconds": time.monotonic() - started,
            "scored_cases": 0, "evaluation_model_calls": 0, "evaluation_model_tokens": 0,
            "evaluation_model_cost_usd": 0, "authoring_model_cost_usd": None,
            "commands": [asdict(command) for command in commands],
            "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(logs.iterdir())},
        }
        (output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(any(command.exit_code for command in commands))


if __name__ == "__main__":
    raise SystemExit(main())
