# Final boundary repair and unchanged comparison

Preserve scored-v2.tar.gz and summary-v2.json at f62739d. Its 48 trials justified
51 skips per mechanism, with zero missed failures; TraceMantle cost 7.476 seconds
more than full execution and 3.368 seconds more than the simple cache. These
negative observations remain separate, never pooled with the next version.

Final review reproduced a contract hole in the newly added deterministic kind:
an approved record naming a model or model revision could satisfy that non-model
check. This did not affect any study record (all explicitly named none), but it
could misclassify future model execution. Two regressions fail against 556cfd8.
The repaired comparison requires both model and model_revision to be the literal
none for deterministic maintenance. Existing behavioral, routing, static and
immutable-model checks retain their requirements. A preliminary tokenizer-name
probe was not adopted: a local heuristic tokenizer is legitimately deterministic,
so its presence alone does not establish model execution. That exploratory output
is retained, with the two justified before/after model-identity regressions.

Implementation: a72a2d82298fc44894b5ee4858aed87437d26869. Thirty focused scope
regressions, all 16 consumer preflight cases and the ten approval controls pass.
Freeze this amendment before the final scores. Repeat exactly the same 16 cases,
three repetitions, cyclic A/B/C order then independent D, metrics, resources and
20-minute scoring cap. Create a fresh measured seed. No workload, input scope,
acceptance criterion or runtime tactic changes. The additional full comparison
and clean reproduction are research costs; prior scores remain intact.
