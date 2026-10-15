"""Import verified Promptfoo 0.118.10 and 0.124.1 JSON exports, results schema 3.

No providers, assertions, extension hooks or source code are executed here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from tracemantle.evidence import Evidence, evidence_from_dict
from tracemantle.storage import EvidenceError, decode_json, digest

VERSION = '0.118.10'
ADAPTER = f'promptfoo/{VERSION}/results-v3/adapter-v1'
SUPPORTED_VERSIONS = frozenset({VERSION, '0.124.1'})
_ROOT_FIELDS = {'evalId', 'results', 'config', 'shareableUrl', 'metadata'}
_RESULT_FIELDS = {'version', 'timestamp', 'prompts', 'results', 'stats'}
_ROW_FIELDS = {'cost', 'error', 'failureReason', 'gradingResult', 'id', 'latencyMs', 'metadata', 'namedScores', 'prompt', 'promptId', 'promptIdx', 'provider', 'response', 'score', 'success', 'testCase', 'testIdx', 'vars'}


@dataclass(frozen=True, slots=True)
class ImportedExport:
    artifact_sha256: str
    records: tuple[Evidence, ...]
    issues: tuple[str, ...]


def import_promptfoo(raw: bytes, bindings: dict[str, Any]) -> ImportedExport:
    data = decode_json(raw)
    guidance = ' Export canonical records with --input-format neutral for other formats.'
    if not isinstance(data, dict) or not _ROOT_FIELDS <= set(data):
        raise EvidenceError('Unsupported Promptfoo export: expected the verified JSON export envelope.' + guidance)
    version = data['metadata'].get('promptfooVersion') if isinstance(data['metadata'], dict) else None
    if not isinstance(version, str) or version not in SUPPORTED_VERSIONS:
        raise EvidenceError('Unsupported Promptfoo version; supported packages: 0.118.10 and 0.124.1 (results schema 3).' + guidance)
    current = version == '0.124.1'
    if set(data) - _ROOT_FIELDS - ({'vars', 'runtimeOptions'} if current else set()):
        raise EvidenceError('Unsupported Promptfoo export fields.' + guidance)
    if current and (('vars' in data and (not isinstance(data['vars'], list) or not all(isinstance(v, str) for v in data['vars'])))
                    or ('runtimeOptions' in data and not isinstance(data['runtimeOptions'], dict))):
        raise EvidenceError('Promptfoo vars must be an array of names and runtimeOptions an object.' + guidance)
    result = data['results']
    if not isinstance(result, dict) or set(result) != _RESULT_FIELDS or type(result['version']) is not int or result['version'] != 3:
        raise EvidenceError('Unsupported Promptfoo results schema; expected version 3.' + guidance)
    rows = result['results']
    if not isinstance(rows, list) or not rows or len(rows) > 10000:
        raise EvidenceError('Promptfoo results must be a nonempty array of at most 10000 rows.')
    if not isinstance(bindings, dict) or set(bindings) != {'schema_version', 'rows'} or type(bindings['schema_version']) is not int or bindings['schema_version'] != 1 or not isinstance(bindings['rows'], dict):
        raise EvidenceError('Import bindings require schema_version=1 and a rows mapping keyed by export result ID.')
    artifact = hashlib.sha256(raw).hexdigest()
    records = []
    issues = []
    ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - _ROW_FIELDS - ({'tokenUsage'} if current else set()) or not {'id', 'success', 'testCase', 'provider', 'response'} <= row.keys():
            raise EvidenceError('Unsupported Promptfoo result fields.' + guidance)
        if type(row['success']) is not bool or not isinstance(row['id'], str) or row['id'] in ids:
            raise EvidenceError('Promptfoo success must be boolean and result IDs must be unique strings.')
        ids.add(row['id'])
        if not isinstance(row['testCase'], dict) or not isinstance(row['provider'], dict) or not isinstance(row['response'], dict):
            raise EvidenceError('Promptfoo testCase, provider and response must be objects.')
        grading = row.get('gradingResult')
        if grading is not None and (not isinstance(grading, dict) or type(grading.get('pass')) is not bool):
            raise EvidenceError('Promptfoo gradingResult.pass must be boolean.')
        if grading is not None and grading['pass'] != row['success']:
            raise EvidenceError('Promptfoo success conflicts with gradingResult.pass.')
        if current:
            failure = row.get('failureReason')
            if type(failure) is not int or failure not in {0, 1, 2}:
                raise EvidenceError('Promptfoo 0.124.1 requires failureReason 0 (none), 1 (assertion) or 2 (error).')
            if (row['success'] and failure != 0) or (failure == 1 and grading is None):
                raise EvidenceError('Promptfoo failureReason conflicts with success or missing assertion grading.')
            if 'tokenUsage' in row and not isinstance(row['tokenUsage'], dict):
                raise EvidenceError('Promptfoo tokenUsage must be an object.')
        components = (grading or {}).get('componentResults', [])
        if not isinstance(components, list):
            raise EvidenceError('Promptfoo gradingResult.componentResults must be an array.')
        model_judgment = False
        for component in components:
            if not isinstance(component, dict):
                raise EvidenceError('Promptfoo gradingResult.componentResults entries must be objects.')
            assertion = component.get('assertion', {})
            if not isinstance(assertion, dict):
                raise EvidenceError('Promptfoo componentResults.assertion must be an object.')
            assertion_type = assertion.get('type', '')
            if not isinstance(assertion_type, str):
                raise EvidenceError('Promptfoo componentResults.assertion.type must be a string.')
            model_judgment |= assertion_type == 'llm-rubric'
        if row['id'] not in bindings['rows']:
            issues.append(f"Unknown identity for result {row['id']}; no evidence record created.")
            continue
        bound = bindings['rows'][row['id']]
        if not isinstance(bound, dict):
            raise EvidenceError('Each result binding must be an evidence object.')
        state = 'pass' if row['success'] else ('fail' if grading else 'infrastructure-error')
        if current and not row['success']:
            state = {0: 'unknown', 1: 'fail', 2: 'infrastructure-error'}[row['failureReason']]
        record = {**bound, 'schema_version': 1, 'kind': 'check-evidence', 'state': state,
                  'artifact_sha256': artifact, 'fixture_sha256': digest(row['testCase']),
                  'configuration_sha256': digest(data['config']), 'observed_at': result['timestamp'],
                  'adapter': f'promptfoo/{version}/results-v3/adapter-v1', 'runner': f'promptfoo/{version}',
                  'model': row['provider'].get('id', 'unknown'),
                  'reason': str((grading or {}).get('reason') or row.get('error') or 'Evaluator reported success')}
        # A generic export observes responses, not the invocation of a skill.
        record['observation_method'] = 'model-judgment' if model_judgment else 'unknown'
        records.append(evidence_from_dict(record))
    if set(bindings['rows']) - ids:
        raise EvidenceError('Bindings contain result IDs absent from the export.')
    return ImportedExport(artifact, tuple(records), tuple(issues))


def adapt(export_bytes: bytes, bindings: dict[str, Any]) -> list[Evidence]:
    """Adapter-contract entry point. Rows without a binding yield no record;
    ``import_promptfoo`` additionally reports them as issues."""
    return list(import_promptfoo(export_bytes, bindings).records)
