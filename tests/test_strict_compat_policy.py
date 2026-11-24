"""General --strict rejects warnings; it does not assert unverified vendor behavior.

The Cursor block-scalar and VS Code directory notes are historical advice with
no pinned runtime evidence. Only the explicitly named vendor policies promote
them to errors.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tracemantle import validate
from tracemantle.result import Severity

BLOCK = '---\nname: {name}\ndescription: >\n  Use when reviewing release notes for a team.\n---\nBody.\n'
PLAIN = '---\nname: {name}\ndescription: Use when reviewing release notes for a team.\n---\nBody.\n'
CURSOR, VSCODE = 'compat.cursor-description-block-scalar', 'compat.vscode-dirname'


def _skill(root: Path, directory: str, name: str, template: str) -> Path:
    (root / directory).mkdir(parents=True)
    path = root / directory / 'SKILL.md'
    path.write_text(template.format(name=name))
    return path


def _run(path: Path, *args: str) -> tuple[int, dict[str, str], str]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', str(path), '--format', 'json', *args],
                            cwd=path.parent.parent, capture_output=True, text=True, timeout=60)
    diagnostics = json.loads(result.stdout)['results'][0]['diagnostics']
    return result.returncode, {d['rule']: d['severity'] for d in diagnostics}, ' '.join(d['message'] for d in diagnostics)


@pytest.mark.parametrize('args,code,severity', [
    ((), 0, 'info'),
    (('--strict',), 0, 'info'),
    (('--strict-cursor',), 1, 'error'),
    (('--strict', '--strict-cursor'), 1, 'error'),
    (('--strict-vscode',), 0, 'info'),
    (('--target-agent', 'cursor'), 0, 'warning'),
    (('--target-agent', 'cursor', '--strict'), 1, 'warning'),
    (('--target-agent', 'cursor', '--strict-cursor'), 1, 'error'),
    (('--target-agent', 'vscode', '--strict'), 0, None),
    (('--target-agent', 'claude', '--strict', '--strict-cursor'), 0, None),
])
def test_cursor_block_scalar_advice_fails_only_under_a_cursor_policy(tmp_path: Path, args: tuple[str, ...], code: int, severity: str | None) -> None:
    exit_code, rules, messages = _run(_skill(tmp_path, 'notes', 'notes', BLOCK), *args)
    assert (exit_code, rules.get(CURSOR)) == (code, severity)
    if severity == 'error':
        assert '--strict-cursor' in messages and 'unverified' in messages


@pytest.mark.parametrize('args,code,severity', [
    (('--skip-dirname-check',), 0, 'info'),
    (('--skip-dirname-check', '--strict'), 0, 'info'),
    (('--skip-dirname-check', '--strict-vscode'), 1, 'error'),
    (('--skip-dirname-check', '--strict', '--strict-vscode'), 1, 'error'),
    (('--skip-dirname-check', '--target-agent', 'vscode', '--strict'), 0, 'info'),
    (('--skip-dirname-check', '--target-agent', 'vscode', '--strict-vscode'), 1, 'error'),
    (('--skip-dirname-check', '--target-agent', 'cursor', '--strict-vscode'), 0, None),
])
def test_vscode_directory_advice_fails_only_under_the_vscode_policy(tmp_path: Path, args: tuple[str, ...], code: int, severity: str | None) -> None:
    exit_code, rules, messages = _run(_skill(tmp_path, 'folder', 'other-name', PLAIN), *args)
    assert (exit_code, rules.get(VSCODE)) == (code, severity)
    if severity == 'error':
        assert '--strict-vscode' in messages and 'unverified' in messages


def test_standard_directory_rule_still_fails_without_any_vendor_policy(tmp_path: Path) -> None:
    exit_code, rules, _ = _run(_skill(tmp_path, 'folder', 'other-name', PLAIN), '--strict')
    assert exit_code == 1 and rules['frontmatter.name.directory-mismatch'] == 'error'
    assert rules[VSCODE] == 'info'


@pytest.mark.parametrize('config,args,code,severity', [
    ('strict-all = true\n', (), 0, 'info'),
    ('strict-cursor = true\n', (), 1, 'error'),
    ('strict-all = true\nstrict-cursor = true\n', (), 1, 'error'),
    ('target-agent = "cursor"\n', ('--strict',), 1, 'warning'),
    ('[tool.tracemantle]\nstrict-all = true\n', (), 0, 'info'),
])
def test_project_configuration_follows_the_same_policy(tmp_path: Path, config: str, args: tuple[str, ...], code: int, severity: str) -> None:
    path = _skill(tmp_path, 'notes', 'notes', BLOCK)
    (tmp_path / ('pyproject.toml' if config.startswith('[') else 'tracemantle.toml')).write_text(config)
    exit_code, rules, _ = _run(path, *args)
    assert (exit_code, rules.get(CURSOR)) == (code, severity)


def test_strict_still_rejects_real_warnings(tmp_path: Path) -> None:
    path = _skill(tmp_path, 'notes', 'notes', PLAIN)
    path.write_text(path.read_text().replace('Use when reviewing release notes for a team.', 'I help you when reviewing notes.'))
    assert _run(path)[0] == 0
    exit_code, rules, _ = _run(path, '--strict')
    assert exit_code == 1 and 'warning' in rules.values()


def test_library_strict_all_does_not_promote_vendor_advice(tmp_path: Path) -> None:
    path = _skill(tmp_path, 'notes', 'notes', BLOCK)
    severities = {d.rule: d.severity for d in validate(path, strict_all=True).diagnostics}
    assert severities[CURSOR] == Severity.INFO
    assert {d.rule: d.severity for d in validate(path, strict_cursor=True).diagnostics}[CURSOR] == Severity.ERROR
