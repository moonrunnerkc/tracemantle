# Measurement amendment 2

The first scored experiment is preserved in `results-v1.tar.gz` with all 66
trials. It is not relabeled exploratory. Its timing excludes CLI process startup,
and its temporary trusted Git objects were not preserved, although policy,
checker, record and comparison content hashes were retained. These shortcomings
were identified during review, without changing outcome requirements or cases.
Do not pool its observations with the following repeat.

Repeat the same 22 cases, three repetitions and execution order after this
amendment is committed. Pin the repaired TM implementation unchanged at b1f68fb.
The consumer scanner source pins and upstream skill remain unchanged. Freeze the
corrected checker/harness in this commit. Each arm now executes the complete
CLI as a fresh subprocess and records both subprocess wall time and inner-workflow
time. Baseline CLI imports no TM until an integrated operation is requested.
Every temporary trust repository is retained as a Git bundle. New setup evidence
is measured and approved for the changed checker identity before repeating.

This is a measurement/integration correction, not an implementation repair or
changed acceptance requirement. It should not change expected check outcomes.
Any disagreement will be reported. Resource allowance: another 20 minutes for
this repeat, 120 seconds per subprocess; no additional live invocations.
The three originally authorized live invocations have completed and will not be
rerun or pooled with deterministic timings. Authoring/setup time remains missing.
