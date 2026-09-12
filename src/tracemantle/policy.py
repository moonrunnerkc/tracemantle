"""Release policy is read from immutable trusted Git objects, never candidate files."""
from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tracemantle.bundle import normalized_path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from tracemantle.evidence import sha256_field, text_field
from tracemantle.storage import EvidenceError


@dataclass(frozen=True, slots=True)
class RequiredCheck:
    id: str
    kind: str
    inputs: tuple[str, ...]
    coverage_complete: bool
    checker_sha256: str
    configuration_sha256: str
    fixture_sha256: str
    profile_sha256: str
    max_age_seconds: int
    required: bool
    context: tuple[tuple[str, str], ...]
    routing_neighbors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrustedPolicy:
    revision: str
    checks: tuple[RequiredCheck, ...]
    trusted_evidence: frozenset[str]
    sha256: str


def git_blob(root: Path, revision: str, path: str) -> bytes:
    normalized_path(path)
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise EvidenceError('Trusted base revision must be a full 40-character commit SHA, not a moving branch or tag.')
    git = ['git', '--no-pager', '--no-replace-objects', '-C', str(root)]
    try:
        kind = subprocess.run([*git, 'cat-file', '-t', revision], capture_output=True, timeout=30, check=False)
        if kind.returncode or kind.stdout.strip() != b'commit':
            raise EvidenceError('Trusted revision must identify an available commit object.')
        object_name = f'{revision}:{path}'
        size = subprocess.run([*git, 'cat-file', '-s', object_name], capture_output=True, timeout=30, check=False)
        if size.returncode:
            raise EvidenceError(f'Trusted Git object {object_name} is unavailable; fetch the base revision before comparison.')
        if int(size.stdout) > 1024 * 1024:
            raise EvidenceError('Trusted policy/checker exceeds the 1 MiB read limit.')
        result = subprocess.run([*git, 'cat-file', 'blob', object_name], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError(f'Cannot read trusted Git object {revision}:{path}: {exc}') from exc
    if result.returncode:
        raise EvidenceError(f'Trusted Git object {revision}:{path} is not a readable blob.')
    return result.stdout


def load_trusted_policy(root: Path, revision: str, path: str = 'pyproject.toml') -> TrustedPolicy:
    raw = git_blob(root, revision, path)
    try:
        data = tomllib.loads(raw.decode('utf-8'))['tool']['tracemantle']['release']
    except (KeyError, TypeError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise EvidenceError('Trusted base must declare [tool.tracemantle.release] in its TOML configuration.') from exc
    if not isinstance(data, dict) or set(data) != {'schema_version', 'checks', 'trusted_evidence'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise EvidenceError('Release policy requires schema_version=1, checks and trusted_evidence.')
    if not isinstance(data['checks'], list) or not data['checks'] or len(data['checks']) > 1000:
        raise EvidenceError('Trusted release policy requires 1 to 1000 checks.')
    checks = []
    expected = set(RequiredCheck.__dataclass_fields__) | {'checker_path'}
    for row in data['checks']:
        if not isinstance(row, dict) or set(row) != expected:
            raise EvidenceError('Each trusted check must contain exactly the documented check fields.')
        value: dict[str, Any] = dict(row)
        text_field(value['id'], 'check.id')
        if value['kind'] not in {'static', 'behavioral', 'routing'}:
            raise EvidenceError('Check kind must be static, behavioral or routing.')
        for name in ('coverage_complete', 'required'):
            if type(value[name]) is not bool:
                raise EvidenceError(f'Check {name} must be boolean.')
        if type(value['max_age_seconds']) is not int or not 1 <= value['max_age_seconds'] <= 31536000:
            raise EvidenceError('max_age_seconds must be an integer between 1 and 31536000.')
        for name in ('inputs', 'routing_neighbors'):
            if not isinstance(value[name], list) or not all(isinstance(p, str) for p in value[name]):
                raise EvidenceError(f'Check {name} must be an array of paths.')
            value[name] = tuple(sorted({normalized_path(p) for p in value[name]}))
        if not value['inputs']:
            raise EvidenceError('Each check must declare at least one input.')
        for name in ('checker_sha256', 'configuration_sha256', 'fixture_sha256', 'profile_sha256'):
            sha256_field(value[name], name)
        checker_path = value.pop('checker_path')
        if not isinstance(checker_path, str):
            raise EvidenceError('checker_path must be a path in the trusted base.')
        actual = hashlib.sha256(git_blob(root, revision, checker_path)).hexdigest()
        if actual != value['checker_sha256']:
            raise EvidenceError(f"Trusted checker {checker_path!r} does not match checker_sha256.")
        context = value['context']
        if not isinstance(context, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in context.items()):
            raise EvidenceError('Check context must be a string mapping.')
        if set(context) - {'runner', 'adapter', 'model', 'model_revision', 'permissions', 'tokenizer', 'os', 'python', 'node', 'network', 'sandbox', 'architecture'}:
            raise EvidenceError('Unsupported trusted execution context field.')
        value['context'] = tuple(sorted(context.items()))
        checks.append(RequiredCheck(**value))
    if len({c.id for c in checks}) != len(checks):
        raise EvidenceError('Trusted check IDs must be unique.')
    trusted = data['trusted_evidence']
    if not isinstance(trusted, list) or len(trusted) > 10000:
        raise EvidenceError('trusted_evidence must be an array of at most 10000 digests.')
    return TrustedPolicy(revision, tuple(sorted(checks, key=lambda c: c.id)),
                         frozenset(sha256_field(v, 'trusted_evidence') for v in trusted), hashlib.sha256(raw).hexdigest())
