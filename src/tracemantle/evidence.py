"""Versioned evidence identity, independent of any evaluator execution engine."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from tracemantle.bundle import normalized_path
from tracemantle.storage import EvidenceError, digest

STATES = frozenset({'pass', 'fail', 'unknown', 'skipped', 'infrastructure-error'})
METHODS = frozenset({'static-analysis', 'observed-execution', 'inferred-trace', 'model-judgment', 'unknown'})


def sha256_field(value: Any, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise EvidenceError(f'{name} must be a full lowercase SHA-256 digest.')
    return value


def text_field(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise EvidenceError(f'{name} must be a nonempty string of at most 4096 characters.')
    return value


def timestamp(value: Any) -> datetime:
    text = text_field(value, 'observed_at')
    try:
        result = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise EvidenceError(f'Invalid observed_at timestamp {text!r}.') from exc
    if result.tzinfo is None:
        raise EvidenceError('observed_at requires a timezone.')
    return result


@dataclass(frozen=True, slots=True)
class Evidence:
    check_id: str
    state: str
    bundle_sha256: str
    configuration_sha256: str
    profile_sha256: str
    checker_sha256: str
    fixture_sha256: str
    artifact_sha256: str
    inputs: tuple[tuple[str, str], ...]
    observed_at: str
    observation_method: str
    runner: str
    adapter: str
    model: str
    model_revision: str
    model_immutable: bool
    permissions: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    tokenizer: tuple[tuple[str, str], ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(schema_version=1, kind='check-evidence')
        for name in ('inputs', 'environment', 'tokenizer'):
            result[name] = dict(result[name])
        result['permissions'] = list(self.permissions)
        return result

    @property
    def sha256(self) -> str:
        return digest(self.to_dict())


def evidence_from_dict(value: Any) -> Evidence:
    if not isinstance(value, dict):
        raise EvidenceError('Evidence must be an object.')
    fields = set(Evidence.__dataclass_fields__)
    if set(value) != fields | {'schema_version', 'kind'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != 'check-evidence':
        raise EvidenceError('Evidence requires exactly the version-one identity and execution fields.')
    data = dict(value)
    del data['schema_version'], data['kind']
    for name in fields - {'inputs', 'environment', 'tokenizer', 'permissions', 'model_immutable'}:
        text_field(data[name], name)
        if name.endswith('_sha256'):
            sha256_field(data[name], name)
    if data['state'] not in STATES or data['observation_method'] not in METHODS:
        raise EvidenceError('Unknown evidence state or observation_method.')
    timestamp(data['observed_at'])
    if type(data['model_immutable']) is not bool:
        raise EvidenceError('model_immutable must be a boolean, not a claimed truthy value.')
    for name in ('inputs', 'environment', 'tokenizer'):
        mapping = data[name]
        if not isinstance(mapping, dict) or len(mapping) > 10000 or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise EvidenceError(f'{name} must be a bounded string mapping.')
        data[name] = tuple(sorted(mapping.items()))
    for path, sha in data['inputs']:
        normalized_path(path)
        sha256_field(sha, f'inputs.{path}')
    if set(dict(data['environment'])) - {'os', 'python', 'node', 'network', 'sandbox', 'architecture'}:
        raise EvidenceError('Environment supports only os, python, node, network, sandbox and architecture; do not import secrets.')
    permissions = data['permissions']
    if not isinstance(permissions, list) or len(permissions) > 100 or not all(isinstance(p, str) and p in {'read-bundle', 'write-output', 'network', 'execute-helper'} for p in permissions):
        raise EvidenceError('permissions contains an unsupported capability.')
    data['permissions'] = tuple(sorted(set(permissions)))
    return Evidence(**data)
