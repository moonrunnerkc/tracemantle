"""Import the pinned Promptfoo 0.118.10 JSON export, results schema 3.

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
    if not isinstance(data, dict) or set(data) != _ROOT_FIELDS:
        raise EvidenceError('Unsupported Promptfoo export: expected the pinned JSON export envelope.')
    if not isinstance(data['metadata'], dict) or data['metadata'].get('promptfooVersion') != VERSION:
        raise EvidenceError(f'Unsupported Promptfoo version; this adapter accepts {VERSION} only.')
    result = data['results']
    if not isinstance(result, dict) or set(result) != _RESULT_FIELDS or type(result['version']) is not int or result['version'] != 3:
        raise EvidenceError('Unsupported Promptfoo results schema; expected version 3.')
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
        if not isinstance(row, dict) or set(row) - _ROW_FIELDS or not {'id', 'success', 'testCase', 'provider', 'response'} <= row.keys():
            raise EvidenceError('Unsupported Promptfoo result fields.')
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
        record = {**bound, 'schema_version': 1, 'kind': 'check-evidence', 'state': state,
                  'artifact_sha256': artifact, 'fixture_sha256': digest(row['testCase']),
                  'configuration_sha256': digest(data['config']), 'observed_at': result['timestamp'],
                  'adapter': ADAPTER, 'runner': f'promptfoo/{VERSION}',
                  'model': row['provider'].get('id', 'unknown'),
                  'reason': str((grading or {}).get('reason') or row.get('error') or 'Evaluator reported success')}
        # A generic export observes responses, not the invocation of a skill.
        record['observation_method'] = 'model-judgment' if model_judgment else 'unknown'
        records.append(evidence_from_dict(record))
    if set(bindings['rows']) - ids:
        raise EvidenceError('Bindings contain result IDs absent from the export.')
    return ImportedExport(artifact, tuple(records), tuple(issues))
