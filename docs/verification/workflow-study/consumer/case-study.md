# SARIF maintainer deployment: no measured rerun benefit

TraceMantle now has a working maintainer-operated SARIF report step in its study
branch CI. It executes Trail of Bits' authentic SARIF helper on this project's
real Ruff output, checks finding identities and counts against Ruff JSON, runs
the documented jq severity query, and executes the upstream 24-test suite. It
produces a useful lint severity/rule/file report. This is not Trail of Bits
adoption, an independent customer deployment, or an external audit.

The original implementation, 1.7.0 at `721845b35ef450ebaaf4c7bfb20990db92d0ed3c`,
misclassified four explanatory paths as missing/escaping resources. Independent
template reproduction also found `{baseDir}` unsupported. The first repair is
`b1f68fb13b4fcf4edb43d4eea19e079d132bcd69`: inline path mentions are uncertain,
explicit links still require resources, and a trusted checker can explicitly
interpret `{baseDir}` as the skill root. Authentic upstream bytes are unchanged.
Neither repair claims that arbitrary prose or program dependencies are complete.

The frozen protocol selected six consecutive owner source revisions and 16
controlled changes, with three repetitions: 22 cases and 66 trials. A uses the
existing Ruff rules plus the new report requirements without TM. B independently
executes all required checks. C adds TM and falls back to full execution whenever
reuse is unavailable. Existing CI has no change-based selection or persisted Ruff
cache. Requirements, checkers and resources were equal across arms.

The first scoring run is retained separately. A committed measurement amendment
repeated it with full CLI timing and retained trusted Git objects. The findings
below use only that repeat, checker/harness revision
`42bba507fe5ff13fb8bd10a3d3ed7261b8be20f3`. Decisions were written before each
reference execution. All 66 reference outcomes agree with A and C, with no
outcome disagreements across repetitions. No cases were excluded.

| Observation | Verified count |
|---|---:|
| Natural or historical mistakes discovered | 0 in six source revisions |
| Controlled failing cases | 6, repeated into 18 failing trials |
| TM validator catches | 2 of 6 fault types; 6 of 18 failing trials |
| Existing consumer checks catch | 6 of 6 fault types; 18 of 18 failing trials |
| Required failures missed by integrated workflow | 0 of 18 failing trials |
| Proposed, justified, or incorrect reuse | 0 of each |
| Required maintenance checks executed per arm | 198 of 198 |
| Required scanner gates executed per arm | 66 of 66 |
| Static or live-agent executions avoided | 0 |

The two validator catches were invalid name metadata and a deleted explicitly
linked helper. Python report corruption, malformed transitive jq code, a shared
fixture corruption and an actual scanner finding from an injected unused import
were caught by the unchanged consumer checks. TM's validator did not detect those
four fault types. They were not missed by the integrated workflow because it ran
the full suite. These are injected capabilities tests, not production discoveries.

No skip was proposed, so there is no empirical successful reuse example to verify.
Actual inputs, approval digests and policy compatibility are retained per case.
Forty-eight trials passed the functional reference but had a nonpassing evidence
gate: 24 are intentional trust/context controls and 24 reflect conservative
coverage blocking on otherwise passing inputs. This is the protocol's broad
“unnecessary block” observable, not 48 policy bugs. The report fallback caused
zero incorrect workflow blocks. An unrelated note also forced full execution in
all three trials. Missing, expired, conflicting and unapproved evidence were not
accepted; changing checker/configuration/environment/model identity did not
permit reuse. Hosted model identity was never labeled immutable.

| Resource measurement, 66 trials | Seconds |
|---|---:|
| A: equivalent report workflow, CLI wall time | 21.710 |
| B: independent full reference, CLI wall time | 21.791 |
| C: integrated workflow, CLI wall time | 27.552 |
| C minus A | **+5.842** |
| TM validation/identity/manifest/comparison inside C | 3.007 |
| Existing scanner-only execution within A | 2.000 |
| Entire repeated experiment, including setup/recording | 84.077 |

There was no optimized execution cost reduction: C executed everything. Estimated
operational savings under these observed serial conditions are zero omitted
checks and negative 5.842 seconds per 66 invocations, before amortizing setup.
The original scanner-only workflow is much cheaper than all three augmented
report workflows. The extra report is a new requirement, not a preexisting
savings opportunity. These serial timings do not predict parallel CI critical
paths. The earlier scoring run consumed another 71.840 seconds; two seed report
runs consumed 0.388 and 0.281 seconds internally. Full-reference, clean-reproduction,
repair/test, and live-observation costs are additional research costs, not savings.
Human setup time and authoring model usage were not measured.

Three separately authorized live Codex invocations used the supplied skill and
real clean scan. All three returned the correct zero-finding summary. Each first
tried the absent `python` command, then recovered with `python3` without human
intervention. Their total wall time was 64.939 seconds. Reported usage was
339,112 input tokens (275,968 cached) and 1,249 output tokens. Underlying model
request counts and monetary charges are unavailable. The configured gpt-6-astra
alias has no established immutable backend revision. No behavioral reuse is
claimed. Three identical answers on an empty scan do not test skill routing,
nonempty live reasoning, or future equivalence.

Post-score boundary probes found decoded NUL crashed path resolution and a
`{baseDir}/~/...` suffix inherited legacy home expansion. Three regressions failed
before correction and passed afterward. The intermediate correction at cb29e58 still failed one case because
URL parsing stripped a leading control. The final tokenizer correction at
`7da20adf6e8eb800c87ff9362b51de4ea55aaa4d` passes all 25 reference repair cases. These inputs were not
in the scored set; the earlier implementation's measurements remain distinct.
The final integration also removes a formatting-only lint failure in the timing
revision. See the repair logs and final verification record.

Keeping TM as this workflow's rerun optimizer is not justified by these data.
Its repaired static diagnostics can be useful, but they found no additional
failure that the required consumer checks missed and added recurring cost.
The smallest justified next step is an auditable dependency-intent contract only
if a real consumer needs reuse enough to pay for maintaining it. Do not waive
incomplete coverage to improve this result. The branch keeps the deployed report
and evidence available for review; it has not been merged or published.
