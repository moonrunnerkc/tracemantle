# Scoped automation approval (unreleased)

## Decision before implementation

The trust source is an owner-selected immutable Git commit. Policy schema 1
continues to require `trusted_evidence` and, when present, `required_signers`.
Schema 2 adds an optional `automation` table with explicit public keys, check
IDs, and a maximum approval lifetime. Removing that table restores digest-only
approval. `required_signers` continues to apply to records on either route.

Automation signs a small canonical approval envelope with the existing
OpenSSH/minisign machinery. It binds the complete evidence digest (including
outcome and execution context), policy file digest, trusted commit, check ID,
candidate bundle digest, run ID, run start, issue time and expiration. The
comparison caller must supply the expected run ID and start independently of
candidate artifacts. Approvals are valid only within that run and lifetime;
verification may repeat within the same run. There is no global consumption
ledger. The protected scheduler must never reuse run IDs/start pairs. Key removal
requires selecting the newer trusted base; old immutable bases retain their old
authority. Candidate files cannot select keys or checks.

No current-run exception to behavioral reuse is introduced. Even freshly signed
records retain all existing identity, immutable-model, freshness, dependency,
observation and conflict rules. Approval cannot turn unknown or skipped evidence
into a pass. A malformed approval or unavailable verification tool fails closed.

The reference producer must construct evidence from a trusted observation, check
the result against trusted checker/fixture/configuration identities, and validate
compatibility before signing. It must not sign arbitrary uploaded evidence JSON.
Evaluation is a separate process/job without signing credentials; approval runs
only trusted code and treats evaluation artifacts as bounded data. Deployment
must protect the scheduler, observer transport, trusted checkout, signing job and
key. A signature identifies the approving key holder, not an execution observer.

## Baseline and acceptance checklist

Started from clean `main` at `a5c02e9d7101da85665e75eec471d7dc92bbd4f8`,
equal to fetched `origin/main`. Relative to the supplied `8745c6f` baseline,
two commits add tilde-reference expansion and its cross-platform test fix.
Read the global and repository instructions; no nested instruction files exist.

| Classification | Requirement | Acceptance |
| --- | --- | --- |
| Already resolved | Local file/directory validation; external adapter boundary | Preserve real CLI, JSON and strict-mode tests |
| Usability | Onboarding, help, short README | Clean published and built installs; recorded output; reader walkthrough |
| Intentional protection | Digest allowlist and additional signatures | Legacy signed-but-unapproved records still fail |
| New opt-in authority | No recurring digest commits | Two changed bundles, same policy/base, real signatures; tampering failures |
| Usability | Evaluator-neutral data import | Bounded full-record validation, original bytes, no code execution |
| Compatibility extension | Additional Promptfoo contract | Authentic export, exact version/schema, provenance and negative controls |

No implementation defect is inferred from the request alone. Any reproduced
defect and actual verification results will be recorded in the implementation
handoff. Publishing, pushing and repository-protection changes are out of scope.
