"""Every CLI mode shares one aggregate source-byte budget per batch."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tracemantle import cli_inputs, emit_modes
from tracemantle.parser import ParseError

SKILL = '---\nname: {name}\ndescription: Use when checking the batch byte budget.\n---\n\nBody.\n'


def _skills(root: Path, count: int) -> list[Path]:
    paths = []
    for index in range(count):
        directory = root / f'skill-{index}'
        directory.mkdir(parents=True)
        (directory / 'SKILL.md').write_text(SKILL.format(name=f'skill-{index}'))
        paths.append(directory / 'SKILL.md')
    return paths


def test_files_past_the_budget_yield_parse_errors_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _skills(tmp_path, 3)
    size = len(paths[0].read_bytes())
    monkeypatch.setattr(cli_inputs, 'MAX_SCAN_BYTES', size * 2)
    parsed = list(cli_inputs.parse_batch(paths))
    assert [path for path, _ in parsed] == paths
    assert [isinstance(item, ParseError) for _, item in parsed] == [False, False, True]
    assert 'byte budget' in str(parsed[2][1])


@pytest.mark.parametrize('emit', [
    lambda paths: emit_modes.emit_activation(paths, 'json'),
    lambda paths: emit_modes.emit_graph(paths, 'json'),
    lambda paths: emit_modes.emit_critique_prompts(paths, 'json'),
    lambda paths: emit_modes.emit_agent_reason_packet(paths, 'json', 'claude', 'claude'),
], ids=['activation', 'graph', 'critique-prompt', 'agent-reason'])
def test_emit_modes_report_files_past_the_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str], emit: Callable[[list[Path]], None]) -> None:
    paths = _skills(tmp_path, 2)
    monkeypatch.setattr(cli_inputs, 'MAX_SCAN_BYTES', len(paths[0].read_bytes()))
    with pytest.raises(SystemExit) as exit_info:
        emit(paths)
    assert exit_info.value.code == 1
    errors = json.loads(capsys.readouterr().out)['errors']
    assert [error['path'] for error in errors] == [str(paths[1])]
    assert 'byte budget' in errors[0]['error']
