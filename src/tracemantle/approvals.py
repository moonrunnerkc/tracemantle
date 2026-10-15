"""Run-scoped approval of complete evidence digests by trusted automation keys."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from tracemantle.evidence import Evidence, text_field, timestamp
from tracemantle.policy import TrustedPolicy
from tracemantle.signatures import MAX_SIGNATURE_BYTES, has_required_signature
from tracemantle.storage import EvidenceError, canonical, read_json


def approval_envelope(record: Evidence, policy: TrustedPolicy, *, run_id: str, run_started_at: str,
                      issued_at: str, expires_at: str) -> dict[str, Any]:
    """Build the message to sign after a trusted observer validates the record.

    This only constructs data. It does not observe execution or approve evidence.
    Times must include a timezone; run identity must come from the protected caller.
    """
    return {'schema_version': 1, 'kind': 'automation-approval', 'evidence_sha256': record.sha256,
            'policy_sha256': policy.sha256, 'trusted_revision': policy.revision,
            'check_id': record.check_id, 'bundle_sha256': record.bundle_sha256,
            'run_id': run_id, 'run_started_at': run_started_at, 'issued_at': issued_at, 'expires_at': expires_at}


def verify_approval(record: Evidence, path: Path, policy: TrustedPolicy, *, candidate_sha256: str,
                    run_id: str, run_started_at: str, now: datetime) -> bool:
    """Verify RECORD.approval.json and its signature against the selected base.

    Missing approval returns False. Present malformed, incompatible or unsigned
    approval raises EvidenceError. Disabled authority never reads sidecars.
    Verification is repeatable within one run; callers must not reuse run IDs.
    """
    authority = policy.automation
    if authority is None:
        return False
    approval_path = path.with_name(path.name + '.approval.json')
    if not approval_path.exists():
        return False
    if not run_id or not run_started_at:
        raise EvidenceError('Automation approval requires --approval-run-id and --approval-run-started-at from the protected scheduler.')
    text_field(run_id, 'approval run ID')
    start = timestamp(run_started_at)
    data = read_json(approval_path, max_bytes=MAX_SIGNATURE_BYTES)
    if not isinstance(data, dict) or set(data) != set(approval_envelope(
            record, policy, run_id=run_id, run_started_at=run_started_at, issued_at='', expires_at='')):
        raise EvidenceError('Automation approval requires exactly the documented version-one envelope fields.')
    issued = timestamp(data['issued_at'])
    expires = timestamp(data['expires_at'])
    expected = approval_envelope(record, policy, run_id=run_id, run_started_at=run_started_at,
                                 issued_at=data['issued_at'], expires_at=data['expires_at'])
    if type(data['schema_version']) is not int or data != expected:
        raise EvidenceError('Automation approval does not bind this record, policy, check, bundle and trusted run context.')
    if record.check_id not in authority.checks or record.bundle_sha256 != candidate_sha256:
        raise EvidenceError('Automation approval is outside the trusted check or candidate bundle scope.')
    if not start <= timestamp(record.observed_at) <= issued <= now < expires or (expires - start).total_seconds() > authority.max_age_seconds:
        raise EvidenceError('Automation approval is expired, replayed, future-dated or outside the trusted run lifetime.')
    if not has_required_signature(canonical(data), approval_path, authority.signers):
        raise EvidenceError('Automation approval needs a valid signature from a scoped trusted automation key.')
    return True
