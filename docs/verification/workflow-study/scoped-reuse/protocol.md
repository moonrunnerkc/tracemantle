# Prospective deterministic comparison, cycle 2

Freeze this amendment before scoring. It supplements rather than replaces the
preparation zero-call protocol, consumer supplement 1, amendment 2, v1/v2 archives,
and negative case study. All selected cases are known regressions or controls;
none is held out. The maintainer and the same assistant designed and operated this
study. The full reference is independent of TraceMantle's decision logic, not an
independent external audit.

## Pins and admission

Implementation and integration: **4f7c912f4afe0a49bb75fb3fd6768e3cac68823e**,
TraceMantle 1.7.0 plus unreleased scope repair (core commit ac0ef45).
Upstream skill: Trail of Bits 1f68e03536f7980d4c0e6869596f708043a19443,
authentic bytes/provenance retained in integrations/sarif/vendor. Consumer is
moonrunnerkc/tracemantle's real Ruff SARIF reporting and maintenance workflow.
No upstream adoption, live model execution or behavioral reuse is claimed.

Before this freeze, the pinned implementation passed all 16 one-repetition
preflight cases, including 17 independently checked skips per mechanism; the
separate ten approval controls passed. Earlier setup failures are retained:
noncanonical seed tuple order changed its digest on decode (fixed by canonical
validation), a full-test invocation lacked the activated PATH, and an exploratory
run was invalidated by editing its checker while it ran. None is scored. A trial
with compilation-cache isolation was abandoned before scoring: bytecode caches
do not reuse test outcomes. Existing compilation bytes are instead hashed;
Ruff/pytest result caches and plugin autoload are disabled.

Environment: Linux x86_64, CPython 3.12.3, Ruff 0.16.4, pytest 9.1.1,
PyYAML 6.0.3, jq 1.7, heuristic tokenizer, constrained development installation.
Retain pip freeze, execution identity bytes/hashes and host identity with results.
No new dependency, model or network call is part of an operational invocation.
Fresh setup/installation may require package access. No concurrent source,
installed-runtime modification or competing test/build jobs during scoring.

## Requirements and inputs

Every invocation must freshly run Ruff SARIF and JSON export of src/tests/scripts
with the existing project configuration, then generate Python and documented jq
reports. Match counts and every finding's rule, severity, path, line and message
against Ruff JSON. This is mandatory output generation, never reusable.

Three required checks: bundle-contract, report, upstream-tests. Two are reuse
eligible: contract and upstream suite. Also count the required scanner gate and
its JSON oracle separately. Both maintenance scopes include SKILL.md, helper,
test source, jq document and both fixtures. Source review established that tests
extract documented commands; the fixture and Markdown-to-jq dependencies are
real. Contract presence-only inputs are conservatively content-hashed. Scope
rationale/assumptions live in integrations/sarif/check-scopes.json and the trusted
Git approval repository. A new Python/native module triggers upstream review.
Installed Python/stdlib/compilation bytes, packages, native libraries, checker,
execution configuration and scope bytes participate in per-check compatibility.
No application source file participates in maintenance evidence identity.

## Configurations

A: equivalent current workflow, all three checks, no reuse.
B: identical workflow with a small local JSON content cache, same reviewed scopes
and execution identities. It stores only successful check keys. It promises no
cryptographic approval controls and is not penalized for lacking them.
C: same workflow with TraceMantle manifest/validation, trusted schema-3 policy,
canonical digest approvals, context checks and per-check decisions.
D: independent full execution of every check, no reuse, after B/C decisions.

Each invocation is a fresh CLI process on separate source/skill copies and fresh
output/temp directories. All process startup, hashing, policy/evidence loading,
validation, comparison and output generation count in operational wall time.
Both optimizations use the same measured seed. Seed creation/approval is setup
cost, not free evidence and not an operational saving. Record decision.json
before any check, retain it, then inspect D. Verify selected evidence digest,
complete actual input/execution identity and D outcome for every proposed skip.
Keep D and evaluation setup/copy/recording costs separate from A/B/C.

## Frozen cases and independently expected outcomes

Include the same six consecutive historical source revisions from the earlier
study, oldest five plus deployment control; no revision from that range excluded:
721845b35ef450ebaaf4c7bfb20990db92d0ed3c,
192cfb6d11f3fbf568da16b1ace484fdfead6287,
cd63b4991002258fda2a7f76edec16628056056f,
ce6c4f0cfb78ee82aee6e84fa7aa0ccbe38d2df9,
b1f68fb13b4fcf4edb43d4eea19e079d132bcd69,
and b5d86f339bd25cf85d86f6d6a545159e8a3cc9c3.
The authoritative ordered CASES/HISTORY arrays are in the pinned harness. These
historical project changes should preserve both maintenance checks and pass.
No naturally occurring skill defect has been observed in this sample.

Ten controlled changes use b5d86f3 source and authentic skill as base:

| Case | Expected required failure; expected skips B and C |
|---|---|
| invalid-metadata | Contract fails on integer name; 0 |
| missing-helper | Contract, report and upstream suite fail; 0 |
| changed-helper | Wrong summary total makes report fail; 0 |
| changed-query | Transitive jq syntax makes report/upstream fail; 0 |
| shared-fixture | Fixture with no inherited error fails upstream; 0 |
| description | Passing outputs, changed SKILL bytes rerun both; 0 |
| unrelated | Unused text note preserves checks; 2 |
| scanner-finding | New F401 fails scanner; fresh report contains it; 2 |
| documented-command | Broken SKILL CI_GATE extraction fails upstream; 0 |
| unresolved-module | Unreviewed additional module, upstream reruns; 1 |

The last two are added controls. Others are reused known scenarios. Executable
mode, per-check/shared invalidation, declarations, traversal, unsupported inputs,
legacy behavior and hostile evidence also have repository acceptance regressions.
Approval controls are a separate ten-case preflight: missing, expired, conflicting,
altered, unapproved evidence; changed checker/configuration/environment/declaration;
and a candidate policy replacement which must not change the selected trust.
They are not optimization wins or naturally discovered failures. The irrelevant
old model-change case is excluded because no model participates in this study.

## Order, metrics and decision rule

Run exactly the harness's 16 cases, three repetitions each: 48 trials per arm,
144 required checks per arm, 96 reuse-eligible checks and 48 mandatory reports,
plus 48 scanner gates and 48 JSON oracle executions. Cyclically rotate A/B/C by
(case index + repetition) modulo three, then D; each operational arm occupies
each position once per case. Keep all outcomes. No optional stopping or tuning
against scores. Limit scoring to 20 minutes, subprocesses to 120 seconds; on
infrastructure failure retain partial results and stop, repair with a new version
and amendment, never silently pool versions. No live calls, tokens or model cost.

Caught mistake: a required checker actually rejects the independently specified
fault. Missed failure: C or B passes a required failure found by D. Incorrect skip:
reused outcome with incompatible inputs/trust, or D fails that check. Justified
skip requires both compatible reviewed identity/trust and passing D. A passing
rerun alone is insufficient. Unnecessary block: an intact required check cannot
reuse compatible approved evidence without a documented dependency/trust reason.
Report conservative unresolved-module reruns separately from incorrect blocks.

Report absolute counts first, per-case/all-three-repetition timings, gate overhead,
actual subprocesses, report freshness, seed/setup and additional research costs.
Do not infer parallel-CI wall time from serial sums or convert runtime to labor.
Manual human time is unmeasured; list configuration size, setup steps and fixes.
Positive optimization requires justified skips, zero missed required failures,
and lower measured wall cost after recurring overhead; initial setup must be
reported separately. Equivalent cache skips at lower complexity/cost favor the
cache. A digest-approval benefit is separate from speed. Mixed or negative runtime
results retain optional/experimental reuse; no benchmark expansion to chase gains.
