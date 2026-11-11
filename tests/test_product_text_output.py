"""Human output and destination checks for the evidence commands, through the CLI."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from tests.test_adapters import ROW_ADAPTER, _export
from tests.test_build_plan_acceptance import _cli
from tests.test_build_plan_product import _bundle, _record, _trusted_repository


def test_manifest_text_names_the_bundle_digest_and_file_count(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    text = _cli('manifest', str(bundle))
    digest = json.loads(_cli('manifest', str(bundle), '--format', 'json').stdout)['result']['bundle_sha256']
    assert text.returncode == 0
    assert f'Bundle {digest}: 2 files' in text.stdout


def test_compare_text_lists_check_state_changed_inputs_and_reruns(tmp_path: Path) -> None:
    base = _bundle(tmp_path / 'base')
    record = replace(_record(base), observed_at=datetime.now(timezone.utc).isoformat())
    trusted = tmp_path / 'trusted'
    _trusted_repository(trusted, record)
    revision = subprocess.check_output(['git', '-C', str(trusted), 'rev-parse', 'HEAD'], text=True).strip()
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    (candidate / 'helper.py').write_text('print("changed helper")\n')
    result = _cli('compare', str(base), str(candidate), '--trusted-root', str(trusted), '--base-revision', revision,
                  '--evidence', str(trusted / 'approved.json'))
    assert result.returncode == 4
    lines = result.stdout.splitlines()
    assert lines[0] == 'TraceMantle compare: unknown (exit 4)'
    assert any(line.startswith('validate: unknown; ') for line in lines)
    assert 'Changed inputs: helper.py' in lines
    assert 'Required reruns: validate' in lines


def test_compare_output_inside_the_baseline_is_refused(tmp_path: Path) -> None:
    base = _bundle(tmp_path / 'base')
    record = replace(_record(base), observed_at=datetime.now(timezone.utc).isoformat())
    trusted = tmp_path / 'trusted'
    _trusted_repository(trusted, record)
    revision = subprocess.check_output(['git', '-C', str(trusted), 'rev-parse', 'HEAD'], text=True).strip()
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    result = _cli('compare', str(base), str(candidate), '--trusted-root', str(trusted), '--base-revision', revision,
                  '--evidence', str(trusted / 'approved.json'), '--output', str(base / 'report.txt'), '--format', 'json')
    assert result.returncode == 2
    assert json.loads(result.stdout)['result']['state'] == 'infrastructure-error'
    assert not (base / 'report.txt').exists()


def test_external_adapter_requires_object_bindings(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    adapter = tmp_path / 'adapter.py'
    adapter.write_text(ROW_ADAPTER)
    bindings = tmp_path / 'bindings.json'
    bindings.write_text('[1, 2]')
    result = _cli('import-evidence', str(_export(tmp_path, bundle)), '--bundle', str(bundle), '--store', str(tmp_path / 'store'),
                  '--adapter', str(adapter), '--bindings', str(bindings), '--format', 'json')
    assert result.returncode == 2
    assert 'Import bindings must be a JSON object' in json.loads(result.stdout)['result']['reason']
    assert not (tmp_path / 'store').exists()
