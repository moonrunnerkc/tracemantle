"""Audit a pinned requirements file with pip-audit and report one of three outcomes.

pip-audit exits 1 both when it finds an advisory and when it cannot finish, so
its exit status alone cannot tell a vulnerable dependency from an unreachable
advisory service. This wrapper reads the JSON report instead:

    exit 0  every listed requirement was audited and none has a known advisory
    exit 1  at least one audited requirement has a known advisory
    exit 2  the audit is incomplete: no report, a malformed report, a skipped
            requirement or a requirement missing from the report

An incomplete audit is never reported as clean. Network access is required;
this runs only in explicit development and CI invocations.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

CLEAN, VULNERABLE, INCOMPLETE = 0, 1, 2
_PIN = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)==[^\s;]+$')


@dataclass(frozen=True)
class Outcome:
    code: int
    lines: tuple[str, ...]


def _normalized(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def pinned_names(requirements: str) -> set[str]:
    """Return the normalized names in a file of exact ``name==version`` pins.

    Raises:
        ValueError: a line is not an exact pin, so it could not be audited
            without dependency resolution.
    """
    names = set()
    for line in requirements.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = _PIN.match(line)
        if match is None:
            raise ValueError(f'Not an exact pin: {line!r}')
        names.add(_normalized(match[1]))
    return names


def classify(expected: set[str], report_text: str | None, returncode: int) -> Outcome:
    """Decide the outcome from pip-audit's JSON report and exit status."""
    if report_text is None:
        return Outcome(INCOMPLETE, (f'pip-audit exited {returncode} without writing a report; the audit did not complete.',))
    try:
        report = json.loads(report_text)
        rows = report['dependencies']
        audited = {_normalized(row['name']): row for row in rows}
        skipped = sorted(name for name, row in audited.items() if 'skip_reason' in row or not isinstance(row.get('vulns'), list))
        # pip-audit can list one advisory several times under its aliases.
        findings = list(dict.fromkeys((row['name'], row['version'], vuln['id'], tuple(vuln['fix_versions']))
                                      for row in rows for vuln in row.get('vulns', [])))
    except (ValueError, KeyError, TypeError) as exc:
        return Outcome(INCOMPLETE, (f'pip-audit report is malformed ({type(exc).__name__}: {exc}); the audit did not complete.',))
    missing = sorted(expected - audited.keys())
    if skipped or missing:
        return Outcome(INCOMPLETE, tuple(f'Not audited: {name}' for name in sorted({*skipped, *missing})))
    if findings:
        return Outcome(VULNERABLE, tuple(
            f'{name} {version}: {identifier} (fixed in: {", ".join(fixes) or "no fixed release listed"})'
            for name, version, identifier, fixes in findings))
    if returncode:
        return Outcome(INCOMPLETE, (f'pip-audit exited {returncode} with no advisory in its report; the audit did not complete.',))
    return Outcome(CLEAN, (f'{len(expected)} pinned requirements audited; no known advisories.',))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('requirements', type=Path, help='File of exact name==version pins, such as pip freeze output')
    args = parser.parse_args()
    try:
        expected = pinned_names(args.requirements.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'AUDIT INCOMPLETE: cannot read pinned requirements: {exc}', file=sys.stderr)
        raise SystemExit(INCOMPLETE) from exc
    if not expected:
        print('AUDIT INCOMPLETE: the requirements file lists nothing to audit.', file=sys.stderr)
        raise SystemExit(INCOMPLETE)
    with tempfile.TemporaryDirectory(prefix='tracemantle-audit-') as directory:
        report = Path(directory) / 'report.json'
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip_audit', '--requirement', str(args.requirements), '--no-deps', '--disable-pip',
                 '--strict', '--progress-spinner', 'off', '--format', 'json', '--output', str(report)],
                capture_output=True, text=True, timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f'AUDIT INCOMPLETE: pip-audit could not run: {exc}', file=sys.stderr)
            raise SystemExit(INCOMPLETE) from exc
        outcome = classify(expected, report.read_text(encoding='utf-8') if report.is_file() else None, result.returncode)
    label = {CLEAN: 'AUDIT CLEAN', VULNERABLE: 'AUDIT FOUND ADVISORIES', INCOMPLETE: 'AUDIT INCOMPLETE'}[outcome.code]
    stream = sys.stdout if outcome.code == CLEAN else sys.stderr
    print(label, file=stream)
    for line in outcome.lines:
        print(f'  {line}', file=stream)
    if outcome.code == INCOMPLETE and result.stderr.strip():
        print(result.stderr.strip()[-2000:], file=sys.stderr)
    raise SystemExit(outcome.code)


if __name__ == '__main__':
    main()
