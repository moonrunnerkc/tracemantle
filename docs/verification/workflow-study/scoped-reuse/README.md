# Deterministic maintenance reuse study

Read [case-study.md](case-study.md) for the decision, [protocol.md](protocol.md)
and [amendment-2.md](amendment-2.md) / [amendment-3.md](amendment-3.md) for the
prospective design and separately pinned corrections.
The earlier consumer study and preparation reports remain unchanged next door.

On Linux with CPython 3.12, jq 1.7 and this repository's Git history available:

```bash
bash scripts/reproduce_scoped_sarif.sh /tmp/tracemantle-scoped-reproduction
```

The output path must be new. The command clones the local repository, checks out
fe92958c5d7748933560bc4a8f6fe6c4daa9e4cf (implementation a72a2d8 plus frozen
amendment), creates a clean venv, installs constrained tools, actually executes and
approves a new seed, and runs all 48 trials/four arms. It verifies all outcomes and
51 justified skips per optimization. Timing need not match a different machine.
Installation uses package access; execution itself is offline and needs no model,
private project, credential or hosted runner. For offline installation, prepopulate
a wheelhouse and set PIP_NO_INDEX=1 and PIP_FIND_LINKS to its path. No package is
published. The protocol pin contains all actual consumer revisions needed for replay.

Offline evidence review needs only Python's standard library. Extract
scored-v3.tar.gz to a new directory and inspect results/results.json and the per-trial
source/command/output records, decisions and seed/trusted.bundle. summary-v3.json
contains aggregate counts and every trial's timings. Replay may produce different
artifact hashes because temporary absolute paths occur in scanner output; the
recorded commands and corresponding hashes bind each actual run. Scope/input
compatibility is verified separately from output-byte equality. hashes.json inside
the run archive verifies its files; artifact-hashes.json verifies the checked-in
study artifacts. Credentials/private inputs were neither used nor retained; no
redactions affect reproducibility. Absolute local paths and public scanner inputs
are intentionally retained.

scored-v1.tar.gz preserves the first scored implementation and its misleading
integration state in three unresolved-module trials. Its skip/outcome counts
remain valid, and scored-v2.tar.gz preserves the intermediate non-model boundary hole. Neither
is pooled with v3. All model-identity guard regressions are deterministic fixtures,
not live-model evaluation. setup.tar.gz retains exploratory
preflight outcomes, including failures and corrections. verification.tar.gz retains
repository gates, clean installs, clean reproduction and actual-checkout deployment.
The reference checks are independent of TraceMantle decisions; this is a
maintainer-operated study, not an external audit or customer adoption.
