# Cycle 2 amendment: retain and repair an integration state defect

Original scored implementation: 9056f97be9c2b76545e756deabcc67249a8604a1,
whose implementation files equal 4f7c912. All 48 trials are preserved in
scored-v1.tar.gz and summary-v1.json. They are not pooled with the repaired run.
Both mechanisms justified 51 of 96 eligible skips and missed no required failure.
Both cost more than A: cache +4.110 seconds; TraceMantle +7.359 seconds.
This negative result remains valid for that implementation.

Inspection found a reporting defect in all three unresolved-module trials:
the integration correctly forced upstream execution, but displayed the core
comparison's pass state even though its own execution-scope guard was unresolved.
No incorrect skip or missed failure occurred. A preserved assertion against the
original decision fails. The fix makes the integration state unknown whenever
any registered maintenance check lacks reuse eligibility despite a core pass.
The consumer regression now asserts this state. All 16 preflight cases and the
ten separate approval controls passed after the repair.

Repaired implementation: 556cfd8b76a600ccefc32f28d1a193c9f4a2fe9b. Freeze this amendment before rescoring.
Use the identical cases, three repetitions, cyclic order, identities, checkers,
acceptance criteria, metrics and 20-minute cap from protocol.md. The only changes
are the two-line integration state correction and its two-line harness assertion.
Create a fresh actually executed seed because checker identity changed. Do not
change workload, scope, timing method or decision rule to seek a positive result.
The second full experiment is additional research cost, not operational savings.
