"""Data-only import of canonical evidence, independent of evaluator versions."""
from __future__ import annotations

import hashlib
from typing import Any

from tracemantle.evidence import Evidence, evidence_from_dict
from tracemantle.storage import EvidenceError, decode_json

ADAPTER = 'tracemantle/neutral-v1'


def adapt(export_bytes: bytes, bindings: dict[str, Any]) -> list[Evidence]:
    data = decode_json(export_bytes)
    if bindings != {'schema_version': 1, 'rows': {}}:
        raise EvidenceError('Neutral JSON carries complete records; do not supply bindings.')
    if not isinstance(data, dict) or set(data) != {'schema_version', 'records'} or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise EvidenceError('Neutral JSON requires schema_version=1 and records.')
    if not isinstance(data['records'], list) or not 1 <= len(data['records']) <= 10000:
        raise EvidenceError('Neutral JSON requires 1 to 10000 canonical evidence records.')
    artifact = hashlib.sha256(export_bytes).hexdigest()
    # Validate the source fields before assigning importer-owned provenance.
    records = [evidence_from_dict(row) for row in data['records']]
    return [evidence_from_dict(r.to_dict() | {'adapter': ADAPTER, 'artifact_sha256': artifact}) for r in records]
