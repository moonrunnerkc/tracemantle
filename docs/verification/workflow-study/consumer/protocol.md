# Frozen SARIF consumer protocol, supplement 1

This supplements, and does not relabel, the preparation-only protocol. Setup and
original-version failures remain unscored. Freeze this supplement, harness and
measured seed evidence in Git before executing `evaluate` or live calls.

## Deployment and pins

Consumer: moonrunnerkc/tracemantle, maintainer-operated Ruff SARIF reporting.
The vendored Trail of Bits skill is used to process real scanner output from
this project, not merely validated as a copied public repository. Upstream did
not adopt this integration. Authentic upstream pin and per-file hashes are in
`integrations/sarif/vendor/PROVENANCE.json`. Its license remains CC BY-SA 4.0.

Repaired implementation: the full commit resolving `b1f68fb`, recorded below.
Consumer/checker: the full commit resolving `b5d86f3`, recorded below. Tool version
is still 1.7.0 plus the pinned unreleased repair. The earlier 1.7.0 source at
721845b35ef450ebaaf4c7bfb20990db92d0ed3c is reported separately, never pooled.
CPython 3.12.3/Linux, Ruff 0.16.4, PyYAML 6.0.3, pytest 9.1.1, jq 1.6, heuristic
tokenizer. Exact installed packages and system versions accompany results.
The checker binds skill-base-dir explicitly and hashes scanner source,
configuration, checker, interpreter, OS, Ruff version and jq executable.
No author-intent overrides or incomplete-to-complete overrides are permitted.

The selected project has an actual Ruff gate in CI, full scope `src tests scripts`,
without change-based selection or a persisted cache. A runs that existing gate
plus the newly required SARIF report and skill maintenance checks, without TM.
Also report the original scanner-only cost separately: the extra report is a
new requirement and is not a preexisting savings opportunity. B runs the complete
same required checks independently. C adds TM validation, manifest and trusted
comparison, reusing a result only on an overall passing comparison and compatible
external inputs. Never skip from a per-check pass under an unknown overall gate.

## Required outcomes and independent checks

All arms use exactly the same checker, source, skill bytes, resources and limits.
Ruff's configured lint gate remains required. The report must preserve total,
severity counts, rule counts, affected-file count, and each rule/path/line/message
identity against Ruff's separately executed JSON exporter. In this pinned Ruff
format lint diagnostics are error-level. Both empty and nonempty results matter.
The documented jq query must count those errors too. These expectations do not
consult TM. The upstream 24-test suite covers inherited severity, both rule joins,
passing records, and path-preserving deduplication that a clean project scan
cannot demonstrate. Metadata must have the exact consumer skill name and a
nonempty string description; six declared required files must exist.

Required checks are `bundle-contract`, `report` (Python and jq plus independent
JSON oracle), and `upstream-tests`, in addition to the common scanner gate.
Only static SARIF report analysis is eligible for evidence reuse. Upstream unit
tests are deterministic helper execution, never model-behavior evidence.
All skill files are bound in the report record; Python stdlib, interpreter,
scanner source/config, jq binary and checker are external context. The shared
CodeQL fixture is consumed by multiple upstream tests. Markdown references are
not the source of truth for this actual dependency list. No arbitrary imports
or runtime dependencies are declared proven complete; coverage_complete=false.

The seed is an actual successful setup execution, stored with raw outputs and
hashes. Approving its canonical digest is a study-maintainer approval, not an
external attestation. Each isolated trust repository commits that approval and
checker before C reads them. Its full trusted revision is retained per decision.
Trust-fault records below are explicitly injected controls, not observations.

## Cases, inclusion rule, and expected outcomes

Include every consecutive consumer source revision from the original evaluated
721845b through the deployment b5d86f3 inclusive: six revisions, five historical
replays and the deployment control. No revision in that interval is excluded.
The earlier preparation commits become historical *source replay* inputs only;
their previous verification results are not scored. There are no naturally
occurring maintenance changes after freeze available in this sample.

Supplement with the following 16 controlled cases, each based on deployment
source. Mutations are fixed in `mutate()` and `evaluate()` before scoring:

| Case | Independently justified expected outcome |
|---|---|
| invalid-metadata | Integer name violates consumer metadata contract; reject |
| missing-helper | Required linked Python helper deleted; reject |
| changed-helper | Helper adds one to total, SKILL unchanged; report must fail |
| changed-query | Transitive documented jq function syntax corrupted; report and upstream jq tests fail |
| shared-fixture | CodeQL fixture severities changed to none; Python and jq known-one-error tests fail |
| description | Routing trigger wording changes; deterministic output remains correct; no behavioral equivalence claim |
| unrelated | New license-review note has no execution dependency; output remains correct, honest evidence uncertainty may still block reuse |
| checker | Trusted checker identity changes; old evidence cannot pass |
| configuration | Trusted configuration identity changes; old evidence cannot pass |
| environment | Required Python context changes; old evidence cannot pass |
| model | Required model identity changes; old evidence cannot pass, even though this task has no model |
| missing-evidence | No record supplied; full execution required |
| expired-evidence | Injected timestamp two days old against one-day limit; full execution required |
| conflicting-evidence | Injected approved failure conflicts with passing seed; no reuse |
| unapproved-evidence | Digest not approved; no reuse |
| scanner-finding | Real Ruff scan of an injected unused import emits one F401; report must preserve it and scanner gate fail |

No controlled defect is a discovered production mistake. The transitive-query
case is an actual followed SKILL-to-document-to-jq-program dependency. The shared
fixture is an execution dependency beyond the Markdown parser's coverage.
Missing explicit links, encoding/traversal, unresolved variables, symlinks and
transitive deletion/change also have separate repair regressions, not scored
natural cases. No known scored failure will be silently tuned away.

## Order, repetitions, limits and measurements

Run listed cases in order: control, five historical revisions oldest first, then
16 controlled cases in table order. Three repetitions each: 22 cases, 66 trials.
C's JSON decision is written before task/checker execution and before independent
B. Arm order C,A,B for repetitions 0 and 2; C,B,A for repetition 1. Separate
source/skill copies for each arm. Disable Ruff caches, pytest cache/autoload and
Python bytecode writes. No outcome-driven stopping or exclusions. Preserve all
runs, including infrastructure failures. Maximum 20 minutes for deterministic
scoring, 120 seconds per subprocess. Abort at cap and report incomplete data.

Before scoring, record source pins and hashes. Retain commands, exits, output
hashes, check errors, gate reasons, check time, end-to-end time and decisions.
Count exact executed/reused checks and actual commands. For every proposed skip,
inspect B and verify dependencies, identity, freshness and digest approval, not
just passing B. Zero proposed skips means zero empirical reuse validations.
Compare measured serial workflow wall times; do not extrapolate summed durations
to parallel CI. Report scanner-only A cost, augmented A, C, B, setup, and extra
verification separately. The evaluation itself consumes all three arms' resources.
Manual edits/interventions are recorded; human time and authoring model telemetry
are missing and must not be converted from automated runtime.

Caught mistake: a required failure surfaced by validation or a required executed
checker. Report TM validation catches separately from failures caught only by the
unchanged consumer checkers. Missed mistake: C accepts/reuses despite a required
failure established by B. Unnecessary block: correct B plus C's unknown/fail
evidence gate; distinguish this from workflow fallback, which still produces a
report. Avoided rerun: actual omitted required check with approved compatible
prior evidence and independently verified full-reference result. An instruction
to rerun or a hypothetical potential skip is not an avoided execution.

Positive requires justified omissions, no observed missed required failures, and
net measured benefit after recurring overhead; setup amortization must be stated.
Mixed means limited demonstrated benefit with material costs or restrictions.
Negative means no net benefit or incorrect reuse. Inconclusive means insufficient
valid measurements or blocked required execution, with exact missing capability.
Finite repetitions cannot establish future deterministic equivalence.

## Bounded live-agent observation

Installed Codex CLI 0.162.1 is authenticated using ChatGPT. Separately attempt
three read-only, ephemeral executions using the configured gpt-6-astra hosted
alias, one per repetition, with a 120-second wall limit each and no retry. A live
agent reads the authentic SKILL.md and the real deployment SARIF and returns a
JSON severity/total summary. Compare it against the measured independent oracle.
No synthetic provider, labels or traces substitute for these executions. Record
actual JSON event usage when available; model request counts, monetary charges
and immutable backend revision may be unavailable. Cap at three agent invocations
and six wall minutes; no separate paid API key or package publication. Stop on
cap or auth/sandbox denial. This supersedes the preparation's zero-call budget
only for these prospective live observations.

No behavioral reuse is authorized: a hosted alias is mutable. Do not claim the
agent's skill-selection/routing correctness merely because a supplied skill
produced a correct answer. Live observations are reported separately from the
static A/B/C experiment; they cannot improve its savings score.

## Full pins

- b1f68fb13b4fcf4edb43d4eea19e079d132bcd69
- b5d86f339bd25cf85d86f6d6a545159e8a3cc9c3
- Seed canonical record SHA-256 is recorded by the harness; original record file SHA-256: 185c3f4528c0ba5779ea455fef114c07fc93904b0277adc28cb0da14073d46c8
