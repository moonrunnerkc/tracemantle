"""Conservative evidence reuse and a five-state release gate."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from tracemantle.bundle import BundleManifest
from tracemantle.evidence import Evidence, timestamp
from tracemantle.policy import RequiredCheck, TrustedPolicy
from tracemantle.storage import digest

EXIT_CODES = {'pass': 0, 'fail': 1, 'unknown': 4, 'skipped': 5, 'infrastructure-error': 2}


@dataclass(frozen=True, slots=True)
class CheckComparison:
    check_id: str
    state: str
    required: bool
    reasons: tuple[str, ...]
    rerun: bool
    evidence_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class Comparison:
    baseline_sha256: str
    candidate_sha256: str
    trusted_revision: str
    policy_sha256: str
    changed_inputs: tuple[str, ...]
    checks: tuple[CheckComparison, ...]
    state: str
    issues: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.state]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result['exit_code'] = self.exit_code
        result['required_reruns'] = [check.check_id for check in self.checks if check.rerun]
        return result


def _compatible(record: Evidence, check: RequiredCheck, candidate: BundleManifest, baseline: BundleManifest,
                changed: set[str], policy: TrustedPolicy, now: datetime) -> list[str]:
    reasons = []
    if record.sha256 not in policy.trusted_evidence:
        reasons.append('Evidence digest is not approved by the trusted base; self-reported provenance is insufficient.')
    for field in ('configuration_sha256', 'profile_sha256', 'checker_sha256', 'fixture_sha256'):
        if getattr(record, field) != getattr(check, field):
            reasons.append(f'{field} differs from the trusted check identity.')
    if record.bundle_sha256 not in {candidate.sha256, baseline.sha256}:
        reasons.append('Evidence belongs to a different bundle.')
    candidate_files = {f.path: f.sha256 for f in candidate.files}
    baseline_files = {f.path: f.sha256 for f in baseline.files}
    expected_files = candidate_files if record.bundle_sha256 == candidate.sha256 else baseline_files
    bound_inputs = dict(record.inputs)
    if not set(check.inputs) <= bound_inputs.keys() or any(expected_files.get(p) != sha for p, sha in record.inputs):
        reasons.append('Declared input coverage or content digests do not match the evaluated bundle.')
    if check.kind != 'static' and record.observation_method != 'observed-execution':
        reasons.append('Required behavioral evidence needs observed execution; inferred traces and model judgments cannot satisfy it.')
    if check.kind != 'static' and (any(getattr(record, name).lower() == 'unknown' for name in ('runner', 'adapter', 'model', 'model_revision')) or not record.environment or not record.tokenizer):
        reasons.append('Behavioral execution identity or environment/tokenizer assumptions are incomplete.')
    if check.kind == 'static' and record.observation_method != 'static-analysis':
        reasons.append('Static evidence requires a declared static analysis observation.')
    age = (now - timestamp(record.observed_at)).total_seconds()
    if age < -300 or age > check.max_age_seconds:
        reasons.append('Evidence is stale or dated in the future.')
    actual_context = dict(record.environment) | {'runner': record.runner, 'adapter': record.adapter, 'model': record.model,
        'model_revision': record.model_revision, 'permissions': ','.join(record.permissions), 'tokenizer': digest(dict(record.tokenizer))}
    for key, value in check.context:
        if actual_context.get(key) != value:
            reasons.append(f'Execution context {key} differs or is unknown.')
    if record.bundle_sha256 != candidate.sha256:
        if not candidate.complete or not baseline.complete or not check.coverage_complete:
            reasons.append('Dependency coverage is incomplete; repeat the complete relevant suite.')
        governed = set(check.inputs) | set(bound_inputs)
        for _ in range(32):
            expanded = governed | {target for source, target in (*baseline.dependencies, *candidate.dependencies) if source in governed}
            if expanded == governed:
                break
            governed = expanded
        if changed & governed:
            reasons.append('Declared helper, schema or skill inputs changed.')
        if any(p in changed and p in check.routing_neighbors for p in changed) or (check.kind == 'routing' and baseline.description_sha256 != candidate.description_sha256):
            reasons.append('Description/routing inputs changed; rerun this case and its declared neighboring skills.')
        if check.kind != 'static' and (not record.model_immutable or record.model_revision == 'unknown'):
            reasons.append('Hosted model aliases are not immutable model revisions; behavioral reuse is unavailable.')
    return reasons


def compare(baseline: BundleManifest, candidate: BundleManifest, records: tuple[Evidence, ...],
            policy: TrustedPolicy, *, now: datetime | None = None) -> Comparison:
    now = now or datetime.now(timezone.utc)
    before = {f.path: (f.sha256, f.executable) for f in baseline.files}
    after = {f.path: (f.sha256, f.executable) for f in candidate.files}
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    checks = []
    for check in policy.checks:
        matching = sorted((r for r in records if r.check_id == check.id), key=lambda r: (r.observed_at, r.sha256), reverse=True)
        valid = []
        rejected: list[str] = []
        for record in matching:
            rejection = _compatible(record, check, candidate, baseline, changed, policy, now)
            if rejection:
                rejected.extend(rejection)
            else:
                valid.append(record)
        if valid:
            # Conflicting approved records cannot be hidden by choosing a passing row.
            states = {r.state for r in valid}
            state = next(s for s in ('fail', 'infrastructure-error', 'unknown', 'skipped', 'pass') if s in states)
            selected = next(r for r in valid if r.state == state)
            reasons: tuple[str, ...] = (selected.reason,)
            if state == 'skipped' and check.required:
                state = 'unknown'
                reasons = ('Required check was skipped; rerun it.',)
            checks.append(CheckComparison(check.id, state, check.required, reasons, state != 'pass', selected.sha256))
        else:
            reasons = tuple(sorted(set(rejected))) if rejected else ('Missing required evidence.' if check.required else 'No optional evidence supplied.',)
            checks.append(CheckComparison(check.id, 'unknown' if check.required else 'skipped', check.required, reasons, check.required))
    required_states = {c.state for c in checks if c.required}
    state = next((s for s in ('fail', 'infrastructure-error', 'unknown', 'skipped') if s in required_states), 'pass')
    issues = candidate.issues
    if not candidate.complete and state == 'pass':
        state = 'unknown'
    if not required_states:
        state = 'unknown'
        issues += ('Trusted policy has no required checks; release cannot be established.',)
    return Comparison(baseline.sha256, candidate.sha256, policy.revision, policy.sha256,
                      tuple(sorted(changed)), tuple(checks), state, issues)
