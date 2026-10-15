# Reviewed maintenance scopes work; optimization is not worthwhile here

Keep selective reuse experimental and optional. In this small workflow, both the
simple cache and TraceMantle cost more than executing all checks. TraceMantle
provided no additional skips or functional failure detections over the cache.
Its digest-approval controls worked, but this consumer has not demonstrated a
need for them that offsets the maintenance cost.

This is moonrunnerkc/tracemantle's maintainer-operated Ruff-to-SARIF workflow,
using authentic Trail of Bits skill bytes at 1f68e035. It is not upstream adoption,
a customer deployment, an external audit or a live-agent evaluation. The actual
checkout and CI generate fresh scans/reports; historical replay supplies the
bounded study's change history. Prior preparation and negative studies remain
unchanged. The repaired scored implementation is a72a2d82298fc44894b5ee4858aed87437d26869,
with prospective amendment fe92958c5d7748933560bc4a8f6fe6c4daa9e4cf.

The repair adds trusted, reviewed per-check scopes and deterministic maintenance
evidence. Scope bytes bind the existing profile digest; configuration binds
installed runtime files and checker identity. Documentation ambiguity remains
visible without poisoning independent check coverage. Explicit resource errors
still block reuse. The upstream suite consumes SKILL.md commands, jq document,
helper and both fixtures; all are included. Application code is a fresh report
input, not a maintenance-evidence dependency. Existing model restrictions remain.

## Observed results

Six historical project revisions plus ten controlled changes, three repetitions
each: 48 trials per arm. All cases were known beforehand, with no exclusions or
outcome disagreements. There were zero naturally discovered mistakes in the six
source revisions. Seven injected fault types produced 21 failing trials.

| Final repaired study | A: full workflow | B: simple cache | C: TraceMantle | D: independent full |
|---|---:|---:|---:|---:|
| Required check executions | 144/144 | 93/144 | 93/144 | 144/144 |
| Justified skips, eligible denominator | 0/96 | 51/96 | 51/96 | 0/96 |
| Fresh report attempts | 48 | 48 | 48 | 48 |
| Scanner gates / JSON oracles | 48 / 48 | 48 / 48 | 48 / 48 | 48 / 48 |
| CLI wall seconds, all 48 trials | 16.638 | 20.847 | 24.016 | 16.739 |
| Reuse mechanism seconds within CLI | 0 | 8.134 | 11.228 | 0 |

The 51 skips comprise 27 contract checks and 24 executions of the authentic
24-test upstream suite. Each skipped check was independently executed in D,
passed, and had matching reviewed inputs/context; C also selected approved,
fresh canonical evidence. Neither mechanism skipped the current report. Three
application-change trials produced fresh F401 reports with the correct file.
Thirty-nine of 48 report checks passed per arm; nine failed as expected on missing
helper, wrong summary or malformed jq faults. There were no stale reused outputs.

Both optimized workflows caught all 21 required failing trials and missed zero.
TraceMantle's validator itself caught two of seven injected fault types (invalid
metadata and missing helper), six of 21 failing trials, already caught by the
consumer checks. The other five required actual scanner/report/test execution.
Helper, fixture and documented-command changes caused reruns. An unrelated note
preserved both checks. An unreviewed module conservatively reran the upstream
suite in three passing trials for each optimization. There were zero incorrect
skips and zero unexplained blocks of compatible evidence. Evidence does not prove
future determinism or arbitrary closed-scope declarations correct.

Separate approval preflight rejected nine of nine incompatible or unapproved
upstream records/contexts and preserved the trusted decision against one candidate
policy replacement. These are controlled approval tests, not failures attributed
to the unsigned cache, which promises no approval guarantee. No new signature or
model evaluation was performed.

## Costs, corrections and decision

Relative to A, the cache added **4.209 seconds** and TraceMantle **7.378 seconds**;
TraceMantle added **3.168 seconds** over the cache. End-to-end timing includes
startup, hashing, policy/evidence loading and fresh outputs. Runtime/compiled-file
hashing is material against a short helper suite. There are no observed operational
wall-time savings, even before setup. These serial measurements do not predict
parallel CI latency. Do not translate them into human hours.

The measured seed/approval setup took 0.584 seconds, separate from C. The full
four-arm experiment consumed 88.814 seconds: 78.240 operational-arm/reference
seconds plus 10.573 seconds of copying, setup and recording. D's 16.739 seconds is
verification cost, not a saving. The original scored implementation consumed
another 88.546 seconds and remains separately archived. It made the same skips
but displayed a misleading pass in three unresolved-module trials; the retained
regression fails on those decisions. The two-line correction and assertion were
preflighted and prospectively frozen before a second 88.397-second experiment.
Final review then added the explicit non-model identity guard: two regressions
failed on the earlier implementation, while all study records already used none.
The final amendment froze the identical experiment again. All three versions
remain separately archived; their results are not pooled.
Exploratory preflights, full gates, clean installation and clean reproduction
consumed further resources; verification.json records measured portions and marks
unmeasured total research/setup time as missing. The evaluation saved no resources.

Setup required reviewing actual dependency paths and loader assumptions, authoring
two scopes (2,033 bytes), implementing runtime identity, registering checks, running
and approving a seed, and selecting its trusted commit. The generated policy is
1,971 bytes; two records total 3,631 bytes, versus a 180-byte two-key cache. Human effort was
not timed. Checker/tool/scope changes require review and new evidence; approvals
expire after one day. The cache shares scope upkeep but needs no Git approval
policy. CI intentionally runs seed, selective workflow and full verification; it
has no persisted cross-run cache and claims no savings.

The smallest justified next step is to retain ordinary fresh maintenance checks
for this consumer. Keep scoped reuse optional for workflows that already need
approved evidence; do not expand this benchmark or infer speed benefits for more
expensive suites. Reproduction, raw decisions/outputs and separate versions are
linked in [README.md](README.md), with per-case/per-repetition data in
[summary-v3.json](summary-v3.json). Earlier live observations remain separate;
this cycle used zero model calls, tokens or model charges.
