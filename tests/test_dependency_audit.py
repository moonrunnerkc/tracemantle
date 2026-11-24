"""The audit wrapper must never report an incomplete audit as clean.

The report shapes below were captured from pip-audit 2.10.1: a clean run, a
run against PyYAML 5.3, and a run whose requirement is absent from PyPI. A
failed advisory lookup wrote no report at all and still exited 1.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'audit_dependencies.py'
CLEAN_REPORT = {'dependencies': [{'name': 'pyyaml', 'version': '6.0.4', 'vulns': []},
                                 {'name': 'tomli', 'version': '2.4.1', 'vulns': []}], 'fixes': []}
VULNERABLE_REPORT = {'dependencies': [
    {'name': 'pyyaml', 'version': '5.3', 'vulns': [{'id': 'PYSEC-2020-96', 'fix_versions': ['5.3.1'],
                                                    'aliases': ['CVE-2020-1747'], 'description': 'text'}]},
    {'name': 'tomli', 'version': '2.4.1', 'vulns': []}], 'fixes': []}
SKIPPED_REPORT = {'dependencies': [{'name': 'pyyaml', 'version': '6.0.4', 'vulns': []},
                                   {'name': 'tomli', 'skip_reason': 'Dependency not found on PyPI and could not be audited'}],
                  'fixes': []}
EXPECTED = {'pyyaml', 'tomli'}


@pytest.fixture(scope='module')
def audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location('audit_dependencies', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('report,returncode,code,text', [
    (CLEAN_REPORT, 0, 0, 'no known advisories'),
    (VULNERABLE_REPORT, 1, 1, 'PYSEC-2020-96'),
    (None, 1, 2, 'without writing a report'),
    (SKIPPED_REPORT, 0, 2, 'Not audited: tomli'),
    ({'dependencies': [CLEAN_REPORT['dependencies'][0]], 'fixes': []}, 0, 2, 'Not audited: tomli'),
    (CLEAN_REPORT, 1, 2, 'no advisory in its report'),
    ({'unexpected': []}, 0, 2, 'malformed'),
    ({'dependencies': [{'name': 'pyyaml'}, {'name': 'tomli'}]}, 0, 2, 'Not audited: pyyaml'),
], ids=['clean', 'advisory', 'service-unavailable', 'skipped', 'missing-row', 'failed-after-report', 'wrong-shape', 'no-vulns-field'])
def test_outcomes_are_distinct(audit: ModuleType, report: dict[str, object] | None, returncode: int, code: int, text: str) -> None:
    outcome = audit.classify(EXPECTED, None if report is None else json.dumps(report), returncode)
    assert outcome.code == code and text in '\n'.join(outcome.lines)


def test_truncated_report_is_incomplete(audit: ModuleType) -> None:
    assert audit.classify(EXPECTED, json.dumps(CLEAN_REPORT)[:40], 0).code == 2


def test_pins_are_normalized_and_ranges_are_refused(audit: ModuleType) -> None:
    assert audit.pinned_names('# comment\nPyYAML==6.0.4\n\ncharset_normalizer==3.5.1\n') == {'pyyaml', 'charset-normalizer'}
    for line in ('pyyaml>=6.0', 'tracemantle @ file:///src', '-e .', 'tomli==2.4.1; python_version < "3.11"'):
        with pytest.raises(ValueError, match='Not an exact pin'):
            audit.pinned_names(line)


@pytest.mark.parametrize('content', ['', '# nothing pinned\n', 'pyyaml>=6\n'])
def test_command_refuses_input_it_cannot_audit(tmp_path: Path, content: str) -> None:
    requirements = tmp_path / 'requirements.txt'
    requirements.write_text(content)
    result = subprocess.run([sys.executable, str(SCRIPT), str(requirements)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 2 and 'AUDIT INCOMPLETE' in result.stderr and result.stdout == ''
