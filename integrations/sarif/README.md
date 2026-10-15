# Maintainer-operated SARIF reporting

This deployment uses Trail of Bits' pinned SARIF skill to summarize the
TraceMantle project's real Ruff output and check the summary against Ruff's
separate JSON export. It is operated by TraceMantle's maintainer, not an upstream
Trail of Bits deployment or independent customer adoption.

With the repository's constrained development environment active and jq installed:

```sh
python scripts/sarif_workflow.py --integrated --output /tmp/sarif-report
```

The output directory must be new. `scan.stdout` is real scanner SARIF,
`python-report.stdout` is the skill helper's useful severity/rule/file summary,
`jq-report.stdout` is the documented severity query's count, and `run.json`
records commands, hashes, times and acceptance results. The report verifies
finding locations, rule IDs, severity and messages against Ruff JSON. Ruff's
nonzero finding exit is preserved. Empty scans must produce zero totals.
The pinned helper's 24 regression tests also run, including inherited severity
and deduplication cases absent from a clean real scan.

The existing Ruff rules and file scope remain unchanged. There is no existing
change-based selection or persisted Ruff cache in CI. The new reporting step
adds cost to that existing workflow. For equivalent report comparisons, the
baseline runs this same report without TraceMantle (`--integrated` omitted).
The full reference also runs all three required checks in a fresh copy.

TraceMantle validates skill metadata/resources and computes a manifest before
execution. The trusted checker explicitly interprets `{baseDir}` as the selected
skill root; it never expands shell expressions. Ambiguous inline prose remains
incomplete. The consumer falls back to full execution when the overall evidence
gate is unknown. This is a working diagnostic/reporting integration, not a
passing evidence-backed release gate. There are no ignore declarations.

`--evidence-root` and `--trusted-revision` select a digest-approved Git policy
and previously measured report evidence. External scanner source, checker,
configuration and runtime identities must match too. The current authentic
bundle cannot obtain an overall passing reuse decision. Do not override that
limitation to make this integration skip work. The helper regression suite and
bundle contract always run; only report analysis is eligible for evidence reuse.

The vendor directory preserves authentic upstream bytes at
`1f68e03536f7980d4c0e6869596f708043a19443`, including CC BY-SA 4.0 attribution and
per-file hashes. The owner workflow executes reviewed helper code; TraceMantle
itself never executes imported skill contents. This is deterministic helper use,
not evidence of an agent selecting or following the skill.

## Optional maintenance reuse (unreleased cycle 2)

The current Ruff SARIF scan, separate JSON oracle, and Python/jq report always
execute. Only `bundle-contract` and `upstream-tests` are eligible. Both consume
SKILL.md: upstream tests extract documented commands. The reviewed scopes in
[check-scopes.json](check-scopes.json) include the two fixtures, helper, test source
and jq document. Application source is a fresh task input, not a helper-test input.

This Linux deployment hashes Python/stdlib, installed test dependencies, jq and
native libraries, checker code, scope bytes and file executable bits. It disables
pytest plugin autoload, conftest discovery, caching and bytecode writes. Unexpected
Python/native files in resources require upstream execution pending scope review.
The host OS/loader and absence of concurrent modifications remain assumptions.
Other environments need a reviewed identity implementation, not guessed reuse.

With the constrained development environment activated and jq installed:

```bash
python scripts/evaluate_scoped_sarif.py seed --project "$PWD" --output /tmp/sarif-evidence
# Inspect /tmp/sarif-evidence/run, policy.toml and the two scope declarations.
# seed.json identifies the immutable local approval commit made from these results.
python scripts/sarif_workflow.py --integrated --evidence-root /tmp/sarif-evidence \
  --trusted-revision FULL_COMMIT_FROM_SEED_JSON --output /tmp/sarif-current
```

The seed command is maintainer-operated approval of an actual successful run.
It is not an external attestation. Keep its repository outside the evaluated
bundle and select the revision from trusted operator configuration. Regenerate
and review evidence when scopes/context change; expiration is one day. Never
approve an unreviewed candidate policy. Failed or unknown compatibility causes
fresh execution, with reasons retained in decision.json. For comparison, the
small local cache uses `--reuse-cache /tmp/sarif-evidence` with the same identities;
it makes no approval or signature guarantee.

CI exercises seed, selective reuse and a separate full reference on its actual
checkout. This deliberately consumes verification resources and claims no CI
savings. Persisting approved evidence across CI runs remains optional and is not
configured. The bounded study records its operational and research costs separately
under [scoped-reuse](../../docs/verification/workflow-study/scoped-reuse/).
