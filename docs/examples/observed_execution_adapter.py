"""Example adapter for observed-execution-v1 records (docs/schemas/observed-execution-v1.json).

Use with ``tracemantle import-evidence RECORD --adapter observed_execution_adapter.py``.
TraceMantle does not ship or import this file; copy it into your trusted tooling.
"""
from __future__ import annotations

from typing import Any

from tracemantle.adapters import CheckEvidence, EvidenceError, evidence_from_dict
from tracemantle.storage import decode_json

FIELDS = frozenset({'schema_version', 'kind', 'check_id', 'outcome', 'observation_method', 'observed_at', 'bundle_sha256',
                    'inputs_sha256', 'checker_sha256', 'configuration_sha256', 'fixture_sha256', 'profile_sha256',
                    'artifact_sha256', 'context', 'reason'})
CONTEXT_FIELDS = frozenset({'runner', 'model', 'model_revision', 'model_immutable', 'permissions', 'environment', 'tokenizer'})


def adapt(export_bytes: bytes, bindings: dict[str, Any]) -> list[CheckEvidence]:
    record = decode_json(export_bytes)
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise EvidenceError('Expected an observed-execution-v1 record with exactly the documented fields.')
    if type(record['schema_version']) is not int or record['schema_version'] != 1 or record['kind'] != 'observed-execution':
        raise EvidenceError('Unsupported record: expected schema_version 1 and kind "observed-execution".')
    if record['observation_method'] != 'observed-execution':
        raise EvidenceError('observation_method must be "observed-execution"; this adapter does not relabel other evidence.')
    context = record['context']
    if not isinstance(context, dict) or set(context) != CONTEXT_FIELDS:
        raise EvidenceError('context must contain exactly: ' + ', '.join(sorted(CONTEXT_FIELDS)) + '.')
    # evidence_from_dict enforces types, digests, the timestamp and the permission and environment vocabularies.
    # TraceMantle then replaces adapter and artifact_sha256: the canonical artifact is this record's own bytes,
    # which in turn commit to the transcript through the record's artifact_sha256.
    return [evidence_from_dict({
        'schema_version': 1, 'kind': 'check-evidence', 'check_id': record['check_id'], 'state': record['outcome'],
        'bundle_sha256': record['bundle_sha256'], 'inputs': record['inputs_sha256'],
        'checker_sha256': record['checker_sha256'], 'configuration_sha256': record['configuration_sha256'],
        'fixture_sha256': record['fixture_sha256'], 'profile_sha256': record['profile_sha256'],
        'artifact_sha256': record['artifact_sha256'], 'observed_at': record['observed_at'],
        'observation_method': 'observed-execution', 'adapter': 'observed-execution-v1',
        'runner': context['runner'], 'model': context['model'], 'model_revision': context['model_revision'],
        'model_immutable': context['model_immutable'], 'permissions': context['permissions'],
        'environment': context['environment'], 'tokenizer': context['tokenizer'], 'reason': record['reason'],
    })]
