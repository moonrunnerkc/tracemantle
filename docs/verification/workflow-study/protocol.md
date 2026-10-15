# Workflow-value study: admission and preparation protocol

Frozen before verification runs. This is a preparation protocol, not a completed
consumer evaluation protocol. No qualifying consumer has been selected and no
scored runs are authorized by this document. A consumer-specific supplement must
be committed before scoring. Setup findings cannot later become held-out results.

## Identity and admission

Evaluate TraceMantle 1.7.0 at
`721845b35ef450ebaaf4c7bfb20990db92d0ed3c`. Preserve that implementation even if
defects require a separate repaired-version evaluation. Work on
`study/real-workflow-20261015`, separate from the owner's original checkout.

An eligible consumer must have currently maintained, owner-controlled agent
skills, supporting resources, actual useful work, and objective acceptance checks.
Prefer multiple independent skills/checks. Maintainer-operated deployment is
acceptable and must be named as such. Neither a copied upstream repository nor
test fixtures qualify. Do not add artificial helpers to make a project eligible.

Discovery resolves owner repositories' default branches to immutable Git commits,
then inspects recursive trees. Preserve public revisions and exclusions in
`discovery.json`; redact private names, paths and revisions. Inspect known local
skill checkouts separately. An unsuccessful tree request is not absence evidence.
No claim is made about inaccessible repositories or every non-default branch.

The strongest initial lead was swarm-orchestrator: three skills in the April
local checkout. Its current default branch has none. TraceMantle's current
self-host bundle has one file, no packaged helpers, and existing tests primarily
exercise TraceMantle itself with retained critique/graph fixtures. That cannot
establish the requested independent consumer output checks or helper/transitive
workflow benefit. Synced personal skills lack an established source revision,
maintenance workflow and acceptance suite. Stop at preparation if no eligible
consumer can be established; do not describe this as a deployment.

## Preparation runs and limits

Use CPython 3.12 on Linux, fresh virtual environments, dependencies constrained by
the pinned `constraints-dev.txt`, the default offline heuristic tokenizer, and a
separate optional-tokenizer environment. Record installed distributions, system
tools, source identity, commands, exits, stdout/stderr digests and elapsed time.
No live agent or model is part of preparation. Cap live calls at **0**, model
tokens at **0**, and paid evaluation API spend at **$0**. Authoring this study is
not an evaluated agent run; its token/cost telemetry is unavailable.

Run existing full tests with the 80% floor, Ruff, mypy, generated-reference check,
CLI version, and self-host validation/manifest. Existing synthetic evidence tests
remain synthetic. Check both tokenizer environments. Do not change fixtures or
test expectations on failure. Limit each command to 15 minutes, total local
verification to 60 minutes, and remote verification to one nonpublishing CI run
(60 minutes elapsed monitoring cap). Preserve failures and skips. No package
publication or protection changes. An unavailable prerequisite is a limitation,
not a reason to weaken a test. Development corrections to the preparation harness
are allowed and recorded; they are not scored observations.

## Required consumer supplement before scoring

Pin the consumer, baseline workflow including its existing cache/test selection,
checkers, configuration, dependencies, environment and runner. Name actual tasks
and acceptance criteria from consumer requirements, with independent expected
outputs. Declare the full dependency scope from execution and source review,
including imports and files outside Markdown discovery. Unproven scope stays
incomplete. Pin model identity honestly; a hosted alias is mutable. No behavioral
reuse claim without actual agent execution and the product's required identity.

Freeze all consecutive genuine revisions in a specified interval before examining
outcomes. Add pinned historical replay and explicitly labeled controlled faults
only to cover missing categories; never count those as natural discoveries. List
every selected revision and any exclusions. The supplement must instantiate:

| Category | Independently expected condition |
| --- | --- |
| Invalid metadata | Consumer loader/schema requirement violated |
| Missing resource | A required, referenced input cannot be opened |
| Helper-only change | Skill unchanged; checks reading helper rerun |
| Transitive change | Checks reading transitive input rerun |
| Shared resource | Every dependent check reruns |
| Description/routing | Routing cases and actual affected neighbors rerun |
| Unrelated change | Compatible approved evidence may remain reusable |
| Checker/config/environment/model | Changed required context prevents reuse |
| Missing/expired/unapproved evidence | No trusted pass can be established |
| Conflicting evidence | Passing record cannot conceal approved adverse result |

The actual paths, mutations, expected outputs and required check IDs must be
committed, not inferred afterward from TraceMantle's decisions. Unsupported
categories are reported as untested, not silently removed.

## Comparisons and accounting

A is the actual existing consumer workflow, including its intelligent selection.
B executes every required check independently of TraceMantle's decision logic.
C uses A's same requirements and checkers plus TraceMantle validation/comparison.
Freeze C's decision artifact before B's output is visible. Run C's selected work,
A, then B in isolated checkouts with separate writable directories and histories.
Disable reference-result caches. Predeclare three repetitions per case and rotate
the A/C execution order by repetition; B always follows the frozen decision.
Keep all repetitions and disagreements, including infrastructure failures.

For each proposed skip, preserve earlier approved evidence, compatible actual
inputs/context, full-reference result and the checker omitted. A fresh pass alone
does not justify reuse. Never promote static helper execution to agent behavior.
Do not use TraceMantle's verdict as the reference expected answer.

A caught mistake violates an independently specified requirement and is blocked
by the evaluated workflow. A missed mistake violates it but the workflow accepts.
An unnecessary block rejects a compatible, approved, passing case without a
requirement-based reason. An avoided rerun is an execution A would actually make
that C omits on justified evidence, verified against B. An incorrect reuse is an
omission with incompatible dependencies/trust/context or a missed required failure.

Record counts and denominators before percentages; natural, historical and
injected mistakes separately; actual checks executed/reused; per-check elapsed
time; measured end-to-end wall time; model calls/tokens/cost when observable;
TraceMantle overhead; setup, manual corrections and study-reference costs. Missing
measurements are null, not zero. No conversion to human hours and no sum of
parallel check times presented as wall-time savings. Research runs consume real
resources and are separate from estimated operational savings.

Positive requires justified reuse, no observed missed required failure, and
measurable net benefit versus A including relevant overhead. Mixed means a
measured benefit with material limits or costs; negative means no net benefit or
unsafe decisions. Inconclusive means insufficient deployment, coverage, ground
truth, access or measurements. Finite repeated observations establish no future
determinism. This is a maintainer study, not an independent external audit.
