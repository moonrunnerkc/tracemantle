"""Keep the implementation ledger collection count aligned with the suite."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = REPO_ROOT / "docs/implementation-status.md"

_LEDGER_PATTERN = re.compile(r"^(\d+)\s+tests cover", re.MULTILINE)
_COLLECT_PATTERN = re.compile(r"(\d+)\s+tests? collected")


def _ledger_claimed_count() -> int:
    match = _LEDGER_PATTERN.search(LEDGER.read_text(encoding="utf-8"))
    assert match, "Implementation ledger must contain a 'N tests cover ...' sentence"
    return int(match.group(1))


def _collected_test_count() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    for line in reversed(result.stdout.strip().splitlines()):
        match = _COLLECT_PATTERN.search(line)
        if match:
            return int(match.group(1))
    raise AssertionError(
        f"could not parse test count from pytest --collect-only output:\n{result.stdout!r}"
    )


def test_ledger_test_count_matches_collected_count() -> None:
    claimed = _ledger_claimed_count()
    collected = _collected_test_count()
    assert claimed == collected, (
        f"Implementation ledger claims {claimed} tests, pytest --collect-only reports "
        f"{collected}. Update the Implementation ledger's 'N tests cover ...' line in the "
        f"same commit that changes the suite size."
    )
