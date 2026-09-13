"""Real-process regressions for plan acceptance boundaries."""
from __future__ import annotations

import cProfile
import json
import os
import pstats
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_build_plan_product import NOW, _bundle, _policy, _record
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.config_loader import ConfigError, load_config
from tracemantle.core.history import LedgerError, ledger_path_for, load_ledger
from tracemantle.parser import parse
from tracemantle.storage import put_record


def _cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', *args], capture_output=True, text=True, env=env, timeout=30)


def test_graph_report_history_parses_source_once(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    profile = tmp_path / 'profile'
    result = subprocess.run([sys.executable, '-m', 'cProfile', '-o', str(profile), '-m', 'tracemantle', str(bundle), '--skip-dirname-check', '--analyze-graph', '--history', '--format', 'json'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    statistics = pstats.Stats(str(profile))
    calls = [value[1] for (filename, _, name), value in statistics.stats.items() if Path(filename).parts[-2:] == ('tracemantle', 'parser.py') and name == 'parse']
    assert calls == [1]
    assert json.loads(result.stdout)['gate']['passed']


def test_manifest_reuses_source_parse(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    profiler = cProfile.Profile()
    profiler.runcall(create_manifest, bundle)
    calls = [value[1] for (filename, _, name), value in pstats.Stats(profiler).stats.items() if Path(filename).parts[-2:] == ('tracemantle', 'parser.py') and name == 'parse']
    assert calls == [1]


def test_cold_offline_tokenizer_is_explicit(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    # requests prefers lowercase proxies; bypass/all-proxy settings and the
    # alternate cache must not leak in from the developer's environment.
    environment = {key: value for key, value in os.environ.items()
                   if not key.lower().endswith('_proxy') and key not in {'TIKTOKEN_CACHE_DIR', 'DATA_GYM_CACHE_DIR'}}
    cache = tmp_path / 'empty-cache'
    cache.mkdir()
    environment.update(TIKTOKEN_CACHE_DIR=str(cache), DATA_GYM_CACHE_DIR=str(cache))
    # Reserve a real local port without listening so no unrelated service can
    # accept the proxy connection, including on Windows.
    with socket.socket() as blocked_proxy:
        blocked_proxy.bind(('127.0.0.1', 0))
        proxy = f'http://127.0.0.1:{blocked_proxy.getsockname()[1]}'
        for key in ('http_proxy', 'https_proxy', 'all_proxy'):
            environment[key] = environment[key.upper()] = proxy
        environment['no_proxy'] = environment['NO_PROXY'] = ''
        result = _cli(str(bundle), '--skip-dirname-check', '--tokenizer', 'tiktoken', '--format', 'json', env=environment)
        assert result.returncode != 0
        assert 'Traceback' not in result.stdout + result.stderr
        assert 'heuristic' in result.stdout + result.stderr
        fallback = _cli(str(bundle), '--skip-dirname-check', '--tokenizer', 'heuristic', '--format', 'json', env=environment)
        assert fallback.returncode == 0
        assert json.loads(fallback.stdout)['tokenizer']['backend'] == 'word-punctuation'


@pytest.mark.parametrize('flag', ['--emit-graph', '--emit-critique-prompt', '--emit-graph-prompt', '--agent-reason', '--activation-hypotheses'])
def test_emit_batch_continues_after_malformed_source(tmp_path: Path, flag: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    broken = tmp_path / 'broken.md'
    broken.write_text('---\nname: a\nname: b\n---\n')
    result = _cli(str(broken), str(bundle), flag, '--format', 'json')
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report['tool'] == 'TraceMantle'
    assert report['errors']
    items = report.get('results', report.get('agent_reason', report.get('activation_reports')))
    assert isinstance(items, list) and len(items) == 1


@pytest.mark.parametrize('field', ['bundle_sha256', 'configuration_sha256', 'entry'])
def test_malformed_history_blocks_final_gate(tmp_path: Path, field: str) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    store = ledger_path_for(bundle / 'SKILL.md')
    record = {'schema_version': 2, 'kind': 'validation-history', 'run_id': 'malformed-test', 'bundle_sha256': 'a' * 64, 'configuration_sha256': 'a' * 64, 'entry': {}}
    record.pop(field)
    original = put_record(store, record)
    result = _cli(str(bundle), '--skip-dirname-check', '--history', '--format', 'json')
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert not report['gate']['passed'] and 'history.read.failed' in result.stdout
    assert original.exists()
    with pytest.raises(LedgerError, match='Malformed history record'):
        load_ledger(store)


def test_namespaced_alias_precedence_and_ambiguity(tmp_path: Path) -> None:
    config = tmp_path / 'pyproject.toml'
    config.write_text('[tool.skillcheck]\nmax-lines=20\n[tool.tracemantle]\nmax_lines=30\n')
    assert load_config(config).max_lines == 30
    config.write_text('[tool.tracemantle]\nmax-lines=20\nmax_lines=30\n')
    with pytest.raises(ConfigError, match='Ambiguous'):
        load_config(config)
    config.write_text('[tool.tracemantle]\nfrontmatter=false\n')
    with pytest.raises(ConfigError, match='must be a table'):
        load_config(config)


def test_unknown_execution_identity_cannot_pass_even_when_approved(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    manifest = create_manifest(bundle)
    record = replace(_record(bundle), model_revision='unknown')
    report = compare(manifest, manifest, (record,), _policy(record), now=NOW)
    assert report.state == 'unknown'
    assert 'incomplete' in ' '.join(report.checks[0].reasons)


def test_graph_budget_rejects_without_traceback(tmp_path: Path) -> None:
    skill = tmp_path / 'SKILL.md'
    skill.write_text('---\nname: control\ndescription: Validates source when asked to check code.\n---\n' + '# heading\n' * 10001)
    result = _cli(str(skill), '--emit-graph', '--format', 'json')
    assert result.returncode == 1
    assert 'budget' in result.stdout.lower() and 'Traceback' not in result.stderr


def test_incomparable_configuration_does_not_reuse_history(tmp_path: Path) -> None:
    from tracemantle.history_store import history_identity
    bundle = _bundle(tmp_path / 'bundle')
    document = parse(bundle / 'SKILL.md')
    assert history_identity(document, {'strict': True}) != history_identity(document, {'strict': False})


def test_alias_expansion_is_bounded_in_real_process(tmp_path: Path) -> None:
    skill = tmp_path / 'SKILL.md'
    aliases = ['a0: &a0 [x, x]'] + [f'a{i}: &a{i} [*a{i-1}, *a{i-1}]' for i in range(1, 30)]
    skill.write_text('---\n' + '\n'.join(aliases) + '\n---\n')
    result = _cli(str(skill), '--format', 'json')
    assert result.returncode == 1
    assert 'limit' in result.stdout and 'Traceback' not in result.stderr


def test_cross_branch_dependency_cycle_is_detected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / 'bundle')
    skill = bundle / 'SKILL.md'
    skill.write_text(skill.read_text() + '\n[A](a.md) [B](b.md)\n')
    (bundle / 'a.md').write_text('[B](b.md)')
    (bundle / 'b.md').write_text('[A](a.md)')
    result = _cli(str(skill), '--skip-dirname-check', '--format', 'json')
    assert result.returncode == 1 and 'references.cycle' in result.stdout
    assert not create_manifest(bundle).complete
