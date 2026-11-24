"""Expected CLI failures under --format json are one parseable error object.

Validation uses envelope schema 2 and the evidence commands schema 1. Every
case runs the real CLI and checks stdout, stderr and the exit status.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = '---\nname: {name}\ndescription: Use when checking structured failures.\n---\nBody.\n'


def _cli(root: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', *args], cwd=root, capture_output=True, input=stdin, timeout=60)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ('alpha', 'beta'):
        (tmp_path / name).mkdir()
        (tmp_path / name / 'SKILL.md').write_text(SKILL.format(name=name))
    (tmp_path / 'empty').mkdir()
    (tmp_path / 'big.json').write_bytes(b' ' * (5 * 1024 * 1024 + 1))
    (tmp_path / 'binary.json').write_bytes(b'{"a": "\x00"}')
    (tmp_path / 'bad.toml').write_text('max-lines = \n')
    (tmp_path / 'format.toml').write_text('format = "json"\ntarget-agent = "nobody"\n')
    (tmp_path / 'separate').mkdir()
    (tmp_path / 'separate' / 'tracemantle.toml').write_text('max-lines = 10\n')
    (tmp_path / 'separate' / 'SKILL.md').write_text(SKILL.format(name='separate'))
    return tmp_path


CASES = {
    'missing-path': (('nowhere',), 'path not found'),
    'no-skills-discovered': (('empty',), 'No SKILL.md files found'),
    'mixed-project-roots': (('alpha', 'separate'), 'Mixed project roots'),
    'missing-config': (('alpha', '--config', 'absent.toml'), 'absent.toml'),
    'malformed-config': (('alpha', '--config', 'bad.toml'), 'Cannot parse'),
    'invalid-configured-value': (('alpha', '--config', 'format.toml'), 'target-agent must be one of'),
    'missing-ingest': (('alpha', '--ingest-critique', 'absent.json'), 'file not found'),
    'oversized-ingest': (('alpha', '--ingest-graph', 'big.json'), 'limit'),
    'binary-ingest': (('alpha', '--ingest-critique', 'binary.json'), 'control character'),
    'ingest-with-many-skills': (('alpha', 'beta', '--ingest-critique', 'absent.json'), 'applies one agent response to one skill'),
    'option-like-revision': (('alpha', '--changed-since=-p'), 'needs a revision'),
    'outside-a-repository': (('alpha', '--changed-since', 'HEAD'), 'git rev-parse failed'),
    'conflicting-modes': (('alpha', '--emit-graph', '--analyze-graph'), 'Cannot use --emit-graph with --analyze-graph'),
    'agent-without-mode': (('alpha', '--critique-agent', 'codex'), '--critique-agent requires'),
    'freshness-option-without-check': (('alpha', '--profile-max-age-days', '3'), 'require --check-profile-freshness'),
    'missing-ledger': (('alpha', '--show-history'), 'No history ledger found'),
}


@pytest.mark.parametrize('name', sorted(CASES))
@pytest.mark.parametrize('selector', [('--format', 'json'), ('--format=json',)], ids=['separate', 'joined'])
def test_expected_failure_is_one_json_error_object(project: Path, name: str, selector: tuple[str, ...]) -> None:
    args, text = CASES[name]
    result = _cli(project, *args, *selector)
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report['tool'] == 'TraceMantle' and report['schema_version'] == 2
    assert report['gate'] == {'passed': False, 'exit_code': 2} and report['results'] == []
    assert len(report['errors']) == 1 and text in report['errors'][0]['error']
    assert b'Traceback' not in result.stderr and b'usage:' not in result.stdout


@pytest.mark.parametrize('name', sorted(CASES))
def test_text_and_quiet_modes_keep_stderr_diagnostics(project: Path, name: str) -> None:
    args, text = CASES[name]
    # format.toml itself selects JSON, so its text case asks for text explicitly.
    plain = ('--format', 'text') if name == 'invalid-configured-value' else ()
    for extra in (plain, ('--quiet', '--format', 'json')):
        result = _cli(project, *args, *extra)
        assert result.returncode == 2
        assert result.stdout == b'' and text.encode() in result.stderr


def test_stdin_ingest_failures_are_structured(project: Path) -> None:
    for payload, text in ((b'\xff\xfe', 'UTF-8'), (b'x' * (5 * 1024 * 1024 + 1), 'cap'), (b'{"a": "\x1b[31m"}', 'control character')):
        result = _cli(project, 'alpha', '--ingest-critique', '-', '--format', 'json', stdin=payload)
        assert result.returncode == 2 and text in json.loads(result.stdout)['errors'][0]['error']


def test_untrusted_text_cannot_inject_terminal_controls(project: Path) -> None:
    hostile = 'gone\x1b[2Jname'
    machine = _cli(project, hostile, '--format', 'json')
    assert b'\x1b' not in machine.stdout
    assert json.loads(machine.stdout)['errors'][0]['error'].endswith(hostile)
    human = _cli(project, hostile)
    assert b'\x1b' not in human.stderr and human.stdout == b''


@pytest.mark.skipif(shutil.which('git') is None, reason='requires git')
def test_unknown_revision_is_structured(project: Path) -> None:
    subprocess.run(['git', 'init', '-q'], cwd=project, check=True, capture_output=True)
    result = _cli(project, 'alpha', '--changed-since', 'no-such-ref', '--format', 'json')
    assert result.returncode == 2
    assert 'does not name a commit' in json.loads(result.stdout)['errors'][0]['error']


def test_json_selected_by_configuration_applies_after_it_loads(project: Path) -> None:
    # format.toml selects JSON, so the invalid value it also carries is
    # reported as JSON even though the command line never asked for it.
    result = _cli(project, 'alpha', '--config', 'format.toml')
    assert result.returncode == 2
    assert 'target-agent' in json.loads(result.stdout)['errors'][0]['error']
    # An explicit flag still wins over the configured format.
    explicit = _cli(project, 'alpha', '--config', 'format.toml', '--format', 'text')
    assert explicit.returncode == 2 and explicit.stdout == b'' and b'target-agent' in explicit.stderr


@pytest.mark.parametrize('args', [('--format', 'yaml', 'alpha'), ('alpha', '--no-such-option', '--format', 'json'),
                                  ('--format', 'json'), ('alpha', '--format')])
def test_unparseable_arguments_stay_conventional_usage_errors(project: Path, args: tuple[str, ...]) -> None:
    result = _cli(project, *args)
    assert result.returncode == 2
    assert result.stdout == b'' and b'usage:' in result.stderr and b'Traceback' not in result.stderr


def test_a_path_after_the_option_terminator_is_not_a_format(project: Path) -> None:
    result = _cli(project, '--format', 'json', '--', '--format=text')
    assert result.returncode == 2
    assert '--format=text' in json.loads(result.stdout)['errors'][0]['error']
    plain = _cli(project, '--', '--format=json')
    assert plain.returncode == 2 and plain.stdout == b'' and b'path not found' in plain.stderr


@pytest.mark.parametrize('args', [('--help',), ('--help', '--format', 'json'), ('alpha', '--format', 'json', '--version')])
def test_help_and_version_stay_conventional(project: Path, args: tuple[str, ...]) -> None:
    result = _cli(project, *args)
    assert result.returncode == 0 and b'Traceback' not in result.stderr
    assert (b'usage:' in result.stdout) if '--help' in args else result.stdout.startswith(b'tracemantle ')


def test_malformed_skill_in_a_batch_remains_a_result(project: Path) -> None:
    (project / 'beta' / 'SKILL.md').write_text('---\nname: [unclosed\n---\n')
    result = _cli(project, 'alpha', 'beta', '--format', 'json')
    report = json.loads(result.stdout)
    assert result.returncode == 1 and 'errors' not in report
    assert [r['valid'] for r in report['results']] == [True, False]


@pytest.mark.parametrize('args,text', [
    (('manifest', 'nowhere'), 'must be a directory'),
    (('import-evidence', 'absent.json', '--bundle', 'alpha', '--store', 'store'), 'Cannot read'),
    (('import-evidence', 'big.json', '--bundle', 'alpha', '--store', 'store'), 'limit'),
    (('import-evidence', 'binary.json', '--bundle', 'alpha', '--store', 'store'), ''),
    (('compare', 'alpha', 'beta', '--trusted-root', '.', '--base-revision', 'main'), 'full 40-character commit SHA'),
    (('migrate-history', 'absent.json', '--store', 'store'), ''),
])
def test_evidence_command_failures_keep_schema_one(project: Path, args: tuple[str, ...], text: str) -> None:
    result = _cli(project, *args, '--format', 'json')
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report['schema_version'] == 1 and report['exit_code'] == 2 and report['command'] == args[0]
    assert report['result']['state'] == 'infrastructure-error' and text in report['result']['reason']
    assert b'Traceback' not in result.stderr


def test_unexpected_programming_errors_are_not_reported_as_input_errors(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tracemantle.cli as cli

    def broken(*_: object) -> list[Path]:
        raise KeyError('implementation defect')

    monkeypatch.setattr(cli, 'resolve_paths', broken)
    monkeypatch.setattr(sys, 'argv', ['tracemantle', str(project / 'alpha'), '--format', 'json'])
    with pytest.raises(KeyError, match='implementation defect'):
        cli.main()
