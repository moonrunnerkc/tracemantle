"""Verified-profile registry and --check-profile-freshness. HTTP goes to a loopback server only."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tracemantle.config_loader import ConfigError
from tracemantle.profile_freshness import (
    SHIPPED_REGISTRY,
    VerifiedProfile,
    docs_last_modified,
    freshness_warnings,
    load_verified_profiles,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / 'skills/tracemantle/SKILL.md'
ENTRY = '''[agents.{agent}]
version = "1.2.3"
checked = "https://example.invalid/releases/1.2.3"
verified_on = {verified_on}
docs_url = "{url}"
confirmed = ["compat.claude-only"]
contradicted = []
'''


class _DocsHandler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        self.server.seen.append((self.command, self.path))  # type: ignore[attr-defined]
        if self.path == '/gone':
            self.send_response(404)
        else:
            self.send_response(200)
            if self.path == '/dated':
                self.send_header('Last-Modified', 'Wed, 01 Jul 2026 08:00:00 GMT')
            elif self.path == '/garbled':
                self.send_header('Last-Modified', 'recently')
        self.end_headers()

    def do_GET(self) -> None:
        self.server.seen.append((self.command, self.path))  # type: ignore[attr-defined]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'page body that must never be requested')

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def docs_server() -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(('127.0.0.1', 0), _DocsHandler)
    server.seen = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _url(server: ThreadingHTTPServer, path: str) -> str:
    return f'http://127.0.0.1:{server.server_address[1]}{path}'


def _registry(tmp_path: Path, *entries: str) -> Path:
    registry = tmp_path / 'verified.toml'
    registry.write_text('schema_version = 1\n\n' + '\n'.join(entries))
    return registry


def _profile(verified_on: date, url: str = 'https://example.invalid/docs') -> VerifiedProfile:
    return VerifiedProfile('claude', '1.2.3', 'v1.2.3', verified_on, url, (), ())


def _validate(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'tracemantle', str(SKILL), '--format', 'json', *extra], capture_output=True, text=True)


def test_shipped_registry_matches_the_advisory_profile_provenance() -> None:
    advisory = json.loads((SHIPPED_REGISTRY.parent / 'compatibility-v1.json').read_text())['vendors']
    shipped = {p.agent: (p.docs_url, p.verified_on.isoformat()) for p in load_verified_profiles()}
    assert shipped == {v['vendor']: (v['source'], v['recorded_at']) for v in advisory}
    # No rule has been checked against a pinned runtime; the registry must not claim otherwise.
    assert all(not p.confirmed and not p.contradicted for p in load_verified_profiles())


def test_profile_older_than_the_limit_is_reported_and_one_at_the_limit_is_not() -> None:
    def dated(url: str) -> datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)

    today = date(2026, 10, 11)
    stale = freshness_warnings((_profile(date(2026, 7, 12)),), max_age_days=90, today=today, last_modified=dated)
    assert len(stale) == 1 and '91 days ago (limit 90)' in stale[0] and 'claude' in stale[0]
    assert freshness_warnings((_profile(date(2026, 7, 13)),), max_age_days=90, today=today, last_modified=dated) == []


def test_newer_docs_page_is_reported_even_when_the_entry_is_recent() -> None:
    def dated(url: str) -> datetime:
        return datetime(2026, 10, 10, 23, 30, tzinfo=timezone.utc)

    warnings = freshness_warnings((_profile(date(2026, 10, 9)),), max_age_days=90, today=date(2026, 10, 11), last_modified=dated)
    assert len(warnings) == 1 and 'modified on 2026-10-10' in warnings[0]
    assert freshness_warnings((_profile(date(2026, 10, 10)),), max_age_days=90, today=date(2026, 10, 11), last_modified=dated) == []


def test_unchecked_docs_page_is_reported_rather_than_treated_as_fresh() -> None:
    def unreachable(url: str) -> datetime:
        raise OSError('network is unreachable')

    profile = (_profile(date(2026, 10, 10)),)
    failed = freshness_warnings(profile, max_age_days=90, today=date(2026, 10, 11), last_modified=unreachable)
    assert len(failed) == 1 and 'could not check' in failed[0] and 'network is unreachable' in failed[0]
    silent = freshness_warnings(profile, max_age_days=90, today=date(2026, 10, 11), last_modified=lambda url: None)
    assert len(silent) == 1 and 'no Last-Modified header' in silent[0]


def test_docs_check_sends_only_head_requests(docs_server: ThreadingHTTPServer) -> None:
    assert docs_last_modified(_url(docs_server, '/dated')) == datetime(2026, 7, 1, 8, tzinfo=timezone.utc)
    assert docs_last_modified(_url(docs_server, '/undated')) is None
    with pytest.raises(OSError):
        docs_last_modified(_url(docs_server, '/gone'))
    with pytest.raises(ValueError):
        docs_last_modified(_url(docs_server, '/garbled'))
    assert [method for method, _ in docs_server.seen] == ['HEAD'] * 4  # type: ignore[attr-defined]


def test_cli_freshness_warnings_leave_the_report_and_exit_code_unchanged(tmp_path: Path, docs_server: ThreadingHTTPServer) -> None:
    registry = _registry(tmp_path,
                         ENTRY.format(agent='claude', verified_on='2026-04-20', url=_url(docs_server, '/dated')),
                         ENTRY.format(agent='cursor', verified_on='2026-04-20', url=_url(docs_server, '/gone')))
    plain = _validate()
    checked = _validate('--check-profile-freshness', '--profile-registry', str(registry), '--profile-max-age-days', '30')
    assert plain.returncode == checked.returncode == 0
    assert checked.stdout == plain.stdout
    assert 'Profile' not in plain.stderr
    assert 'warning: Profile claude was verified on 2026-04-20' in checked.stderr and '(limit 30)' in checked.stderr
    assert 'warning: Profile claude:' in checked.stderr and 'modified on 2026-07-01' in checked.stderr
    assert 'warning: Profile cursor: could not check' in checked.stderr
    assert {method for method, _ in docs_server.seen} == {'HEAD'}  # type: ignore[attr-defined]


def test_cli_freshness_check_is_scoped_by_target_agent(tmp_path: Path, docs_server: ThreadingHTTPServer) -> None:
    registry = _registry(tmp_path,
                         ENTRY.format(agent='claude', verified_on='2026-04-20', url=_url(docs_server, '/claude')),
                         ENTRY.format(agent='cursor', verified_on='2026-04-20', url=_url(docs_server, '/cursor')))
    checked = _validate('--check-profile-freshness', '--profile-registry', str(registry), '--target-agent', 'cursor')
    assert 'Profile cursor' in checked.stderr and 'Profile claude' not in checked.stderr
    assert [path for _, path in docs_server.seen] == ['/cursor']  # type: ignore[attr-defined]


@pytest.mark.parametrize('content,message', [
    ('schema_version = 2\n[agents.claude]\n', 'schema_version = 1'),
    ('schema_version = 1\n', 'at least one'),
    ('schema_version = 1\n[agents.claude]\nversion = "1"\n', 'must contain exactly'),
    ('schema_version = 1\n' + ENTRY.format(agent='claude', verified_on='"2026-04-20"', url='https://example.invalid'), 'TOML date'),
    ('schema_version = 1\n' + ENTRY.format(agent='claude', verified_on='2026-04-20', url='file:///etc/hostname'), 'http or https'),
    ('schema_version = 1\n' + ENTRY.format(agent='claude', verified_on='2026-04-20', url='https://example.invalid').replace('"1.2.3"', '""'), 'version must be a nonempty string'),
    ('schema_version = 1\n' + ENTRY.format(agent='claude', verified_on='2026-04-20', url='https://example.invalid').replace('contradicted = []', 'contradicted = "none"'), 'array of rule IDs'),
    ('schema_version = [1\n', 'not valid TOML'),
])
def test_malformed_registry_is_rejected_with_the_field_to_fix(tmp_path: Path, content: str, message: str) -> None:
    registry = tmp_path / 'verified.toml'
    registry.write_text(content)
    with pytest.raises(ConfigError, match=message):
        load_verified_profiles(registry)


def test_cli_rejects_a_malformed_registry_and_orphaned_freshness_options(tmp_path: Path) -> None:
    registry = tmp_path / 'verified.toml'
    registry.write_text('schema_version = 1\n')
    broken = _validate('--check-profile-freshness', '--profile-registry', str(registry))
    assert broken.returncode == 2 and 'at least one [agents.NAME] table' in broken.stderr
    orphaned = _validate('--profile-max-age-days', '10')
    assert orphaned.returncode == 2 and 'require --check-profile-freshness' in orphaned.stderr
    nonpositive = _validate('--check-profile-freshness', '--profile-max-age-days', '0')
    assert nonpositive.returncode == 2 and 'at least 1' in nonpositive.stderr
