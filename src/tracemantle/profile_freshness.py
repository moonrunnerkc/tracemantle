"""Age and Last-Modified checks for the verified-profile registry.

The registry records when a human last checked an agent's compatibility claims.
This module reports entries that look out of date. It reads one HTTP header per
profile and nothing else: no page body is fetched and no agent is contacted.
Staleness is advice about the registry, never a statement about a runtime.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tracemantle import __version__
from tracemantle.config_loader import ConfigError
from tracemantle.io_limits import MAX_CONFIG_BYTES, read_guarded_text

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULT_MAX_AGE_DAYS = 90
SHIPPED_REGISTRY = Path(__file__).parent / 'profiles' / 'verified.toml'
_HEAD_TIMEOUT_SECONDS = 10
_FIELDS = {'version', 'checked', 'verified_on', 'docs_url', 'confirmed', 'contradicted'}


@dataclass(frozen=True, slots=True)
class VerifiedProfile:
    agent: str
    version: str
    checked: str
    verified_on: date
    docs_url: str
    confirmed: tuple[str, ...]
    contradicted: tuple[str, ...]


def load_verified_profiles(path: Path = SHIPPED_REGISTRY) -> tuple[VerifiedProfile, ...]:
    """Read a verified-profile registry.

    Raises:
        ConfigError: the file is unreadable, over 1 MiB, not TOML, or an entry
            lacks a documented field or has the wrong type. The message names
            the agent and field to fix.
    """
    try:
        data = tomllib.loads(read_guarded_text(path, max_bytes=MAX_CONFIG_BYTES, what='Profile registry', error_cls=ConfigError))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f'Profile registry {path} is not valid TOML: {exc}') from exc
    agents = data.get('agents')
    if set(data) != {'schema_version', 'agents'} or type(data['schema_version']) is not int or data['schema_version'] != 1 \
            or not isinstance(agents, dict) or not agents:
        raise ConfigError(f'Profile registry {path} requires schema_version = 1 and at least one [agents.NAME] table.')
    profiles = []
    for agent, entry in sorted(agents.items()):
        if not isinstance(entry, dict) or set(entry) != _FIELDS:
            raise ConfigError(f'Profile registry entry {agent!r} must contain exactly: {", ".join(sorted(_FIELDS))}.')
        _require(agent, entry, 'version', str)
        _require(agent, entry, 'checked', str)
        _require(agent, entry, 'docs_url', str)
        if type(entry['verified_on']) is not date:
            raise ConfigError(f'Profile registry entry {agent!r}: verified_on must be a TOML date such as 2026-04-20.')
        if urlsplit(entry['docs_url']).scheme not in {'http', 'https'}:
            raise ConfigError(f'Profile registry entry {agent!r}: docs_url must be an http or https URL.')
        for name in ('confirmed', 'contradicted'):
            if not isinstance(entry[name], list) or not all(isinstance(rule, str) and rule for rule in entry[name]):
                raise ConfigError(f'Profile registry entry {agent!r}: {name} must be an array of rule IDs.')
        profiles.append(VerifiedProfile(agent, entry['version'], entry['checked'], entry['verified_on'], entry['docs_url'],
                                        tuple(entry['confirmed']), tuple(entry['contradicted'])))
    return tuple(profiles)


def _require(agent: str, entry: dict[str, Any], name: str, kind: type) -> None:
    if not isinstance(entry[name], kind) or not entry[name]:
        raise ConfigError(f'Profile registry entry {agent!r}: {name} must be a nonempty string.')


def docs_last_modified(url: str) -> datetime | None:
    """Send one HEAD request and return the Last-Modified time, or None when the
    server sends no such header.

    Raises:
        OSError: the request failed or returned an HTTP error status.
        ValueError: the header is not an HTTP date.
    """
    request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': f'tracemantle/{__version__} profile-freshness'})
    with urllib.request.urlopen(request, timeout=_HEAD_TIMEOUT_SECONDS) as response:
        header = response.headers.get('Last-Modified')
    if header is None:
        return None
    modified = parsedate_to_datetime(header)
    return modified if modified.tzinfo else modified.replace(tzinfo=timezone.utc)


def freshness_warnings(profiles: tuple[VerifiedProfile, ...], *, max_age_days: int, today: date,
                       last_modified: Callable[[str], datetime | None] = docs_last_modified) -> list[str]:
    """Describe every profile that is older than ``max_age_days`` or whose docs
    page reports a later Last-Modified date. An unreachable page or a missing
    header is reported too, so an unchecked profile is never presented as fresh."""
    warnings = []
    for profile in profiles:
        age = (today - profile.verified_on).days
        if age > max_age_days:
            warnings.append(f'Profile {profile.agent} was verified on {profile.verified_on}, {age} days ago (limit {max_age_days}). '
                            f'Re-verify it with the checklist in docs/profiles.md.')
        try:
            modified = last_modified(profile.docs_url)
        except (OSError, ValueError) as exc:
            warnings.append(f'Profile {profile.agent}: could not check {profile.docs_url} ({exc}); only the recorded date was evaluated.')
            continue
        if modified is None:
            warnings.append(f'Profile {profile.agent}: {profile.docs_url} sent no Last-Modified header; only the recorded date was evaluated.')
        elif modified.astimezone(timezone.utc).date() > profile.verified_on:
            warnings.append(f'Profile {profile.agent}: {profile.docs_url} was modified on {modified.astimezone(timezone.utc).date()}, '
                            f'after the {profile.verified_on} verification. Re-verify it with the checklist in docs/profiles.md.')
    return warnings
