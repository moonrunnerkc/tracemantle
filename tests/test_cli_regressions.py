"""CLI regressions reproduced through a real ``python -m tracemantle`` subprocess."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.test_build_plan_product import FIXTURES, _bundle

SKILL = '---\nname: demo-skill\ndescription: Use when checking command line regressions in a demo skill.\n---\n\nBody text.\n'


def _cli(*args: str, cwd: Path, stdin: bytes | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', *args], cwd=cwd, input=stdin,
                            capture_output=True, timeout=60)
    return subprocess.CompletedProcess(result.args, result.returncode, result.stdout.decode('utf-8'), result.stderr.decode('utf-8'))


def _skill(root: Path, name: str = 'demo-skill') -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text(SKILL.replace('demo-skill', name))
    return directory / 'SKILL.md'


def test_malformed_nested_pyproject_is_a_clean_configuration_error(tmp_path: Path) -> None:
    (tmp_path / 'tracemantle.toml').write_text('')
    skill = _skill(tmp_path / 'skills')
    (skill.parent / 'pyproject.toml').write_text('not = [toml\n')
    text = _cli('.', cwd=tmp_path)
    assert text.returncode == 2
    assert 'Traceback' not in text.stderr
    assert 'Cannot parse' in text.stderr and 'pyproject.toml' in text.stderr
    envelope = _cli('.', '--format', 'json', cwd=tmp_path)
    assert envelope.returncode == 2
    report = json.loads(envelope.stdout)
    assert report['gate'] == {'passed': False, 'exit_code': 2}
    assert 'Cannot parse' in report['errors'][0]['error']


def test_configured_agents_do_not_break_plain_validation(tmp_path: Path) -> None:
    (tmp_path / 'tracemantle.toml').write_text('critique_agent = "codex"\ngraph_agent = "cursor"\n')
    _skill(tmp_path)
    result = _cli('demo-skill/SKILL.md', cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'PASS' in result.stdout


def test_explicit_agent_without_its_mode_is_still_a_usage_error(tmp_path: Path) -> None:
    _skill(tmp_path)
    result = _cli('demo-skill/SKILL.md', '--critique-agent', 'codex', cwd=tmp_path)
    assert result.returncode == 2
    assert '--critique-agent requires' in result.stderr


def test_configured_agent_selects_the_emitted_prompt(tmp_path: Path) -> None:
    (tmp_path / 'tracemantle.toml').write_text('critique_agent = "codex"\n')
    _skill(tmp_path)
    configured = _cli('demo-skill/SKILL.md', '--emit-critique-prompt', cwd=tmp_path)
    explicit = _cli('demo-skill/SKILL.md', '--emit-critique-prompt', '--critique-agent', 'codex', cwd=tmp_path)
    assert configured.returncode == explicit.returncode == 0
    assert configured.stdout == explicit.stdout


def test_lone_surrogate_in_imported_export_is_escaped_in_text_output(tmp_path: Path) -> None:
    export = json.loads((FIXTURES / 'upstream/promptfoo-0.124.1/export.json').read_text(encoding='utf-8'))
    export['results']['results'][0]['id'] = '\ud800\x1b]0;x\x07'
    source = tmp_path / 'export.json'
    source.write_text(json.dumps(export), encoding='utf-8')
    bundle = _bundle(tmp_path / 'bundle')
    output = tmp_path / 'report.txt'
    result = _cli('import-evidence', str(source), '--bundle', str(bundle), '--store', str(tmp_path / 'store'),
                  '--output', str(output), cwd=tmp_path)
    assert result.returncode == 4, result.stderr
    assert 'Traceback' not in result.stderr
    report = output.read_text(encoding='utf-8')
    assert '\\ud800\\x1b]0;x\\x07' in report
    assert '\x1b' not in report
    assert not list(tmp_path.glob('.pending-*'))


def test_output_file_accepts_identical_rewrites_and_refuses_different_content(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    output = tmp_path / 'manifest.json'
    first = _cli('manifest', str(bundle), '--format', 'json', '--output', str(output), cwd=tmp_path)
    again = _cli('manifest', str(bundle), '--format', 'json', '--output', str(output), cwd=tmp_path)
    assert first.returncode == again.returncode == 0
    original = output.read_bytes()
    assert json.loads(original)['command'] == 'manifest'
    (bundle / 'helper.py').write_text('print("changed")\n')
    changed = _cli('manifest', str(bundle), '--format', 'json', '--output', str(output), cwd=tmp_path)
    assert changed.returncode == 2
    assert 'already exists with different contents' in changed.stdout
    assert output.read_bytes() == original
    assert not list(tmp_path.glob('.pending-*'))


def test_explained_score_reasons_escape_description_controls(tmp_path: Path) -> None:
    directory = tmp_path / 'demo-skill'
    directory.mkdir()
    (directory / 'SKILL.md').write_text('---\nname: demo-skill\ndescription: "Use\\u0085when reviewing demo files for teams."\n---\n\nBody.\n',
                                        encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'demo-skill/SKILL.md', '--explain-score', '--no-color'],
                            cwd=tmp_path, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert b'\xc2\x85' not in result.stdout
    assert b'\\x85' in result.stdout


def test_oversized_stdin_is_reported_as_too_large_not_as_bad_utf8(tmp_path: Path) -> None:
    _skill(tmp_path)
    payload = 'é'.encode() * (3 * 1024 * 1024)
    result = _cli('demo-skill/SKILL.md', '--ingest-critique', '-', cwd=tmp_path, stdin=payload)
    assert result.returncode == 2
    assert 'exceeds' in result.stderr
    assert 'UTF-8' not in result.stderr


def test_missing_graph_response_names_the_graph_file(tmp_path: Path) -> None:
    _skill(tmp_path)
    result = _cli('demo-skill/SKILL.md', '--ingest-graph', 'missing.json', cwd=tmp_path)
    assert result.returncode == 2
    assert 'graph response file not found: missing.json' in result.stderr


def test_quiet_cannot_silence_an_emit_mode(tmp_path: Path) -> None:
    _skill(tmp_path)
    for mode in ('--emit-graph', '--emit-critique-prompt', '--activation-hypotheses', '--agent-reason'):
        result = _cli('demo-skill/SKILL.md', mode, '--quiet', cwd=tmp_path)
        assert result.returncode == 2, mode
        assert result.stdout == ''
        assert f'Cannot use --quiet with {mode}' in result.stderr


def test_terminal_escaping_neutralizes_bidi_and_line_separators() -> None:
    from tracemantle.display import terminal

    assert terminal('ok‮gnp.exe⁦x⁩ y') == 'ok\\u202egnp.exe\\u2066x\\u2069\\u2028y'
    assert terminal('family \U0001f468‍\U0001f469 and ن‌ا') == 'family \U0001f468‍\U0001f469 and ن‌ا'


def test_sarif_report_carries_every_diagnostic_with_its_location(tmp_path: Path) -> None:
    directory = tmp_path / 'skills' / 'demo-skill'
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text('---\nname: Demo_Skill\ndescription: Use when checking SARIF output.\n---\n\nSee [missing](missing.md).\n')
    result = _cli('skills', '--format', 'sarif', cwd=tmp_path)
    assert result.returncode == 1
    log = json.loads(result.stdout)
    assert log['version'] == '2.1.0'
    [run] = log['runs']
    assert run['tool']['driver']['name'] == 'TraceMantle'
    assert run['invocations'] == [{'executionSuccessful': True, 'exitCode': 1}]
    by_rule = {r['ruleId']: r for r in run['results']}
    assert by_rule['references.broken-link']['level'] == 'error'
    location = by_rule['references.broken-link']['locations'][0]['physicalLocation']
    assert location['artifactLocation']['uri'] == 'skills/demo-skill/SKILL.md'
    assert location['region']['startLine'] == 6
    assert {rule['id'] for rule in run['tool']['driver']['rules']} == set(by_rule)
    json_report = json.loads(_cli('skills', '--format', 'json', cwd=tmp_path).stdout)
    assert len(run['results']) == sum(len(r['diagnostics']) for r in json_report['results'])


def test_sarif_levels_and_lineless_diagnostics(tmp_path: Path) -> None:
    from tracemantle.result import Diagnostic, Severity, ValidationResult
    from tracemantle.sarif import format_sarif

    source = tmp_path / 'dir with space' / 'SKILL.md'
    results = [ValidationResult(source, [
        Diagnostic('description.quality-score', Severity.INFO, 'Score 90/100.'),
        Diagnostic('sizing.lines', Severity.WARNING, 'Too long.', line=3),
    ])]
    [run] = json.loads(format_sarif(results, '9.9.9', gate_exit_code=0))['runs']
    note, warning = run['results']
    assert (note['level'], warning['level']) == ('note', 'warning')
    assert 'region' not in note['locations'][0]['physicalLocation']
    assert note['locations'][0]['physicalLocation']['artifactLocation']['uri'] == source.as_uri()
    assert '%20' in source.as_uri()


def test_sarif_is_refused_for_modes_without_a_validation_report(tmp_path: Path) -> None:
    _skill(tmp_path)
    for mode in ('--emit-graph', '--show-history'):
        result = _cli('demo-skill/SKILL.md', mode, '--format', 'sarif', cwd=tmp_path)
        assert result.returncode == 2, mode
        assert f'Cannot use --format sarif with {mode}' in result.stderr
