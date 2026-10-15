# Bundle and release evidence workflow

TraceMantle separates content identity, analysis results and trust. A SHA-256 digest identifies bytes; it does not prove that those bytes are correct or that an execution occurred. The comparison gate uses checks, checker bytes and approval authority anchored to the selected trusted base commit. Start with [local validation](getting-started.md); evidence setup is optional.

Choose a task: [import neutral JSON](#import-evaluator-neutral-json), [approve manually](#trusted-policy), [approve through protected automation](#protected-automation), or [detect helper changes](#detect-helper-changes). Schema-2 automation, neutral imports, Promptfoo 0.124.1, external adapters and optional signers are available in **1.7.0**. Use the [published installation](getting-started.md#install-the-published-validator); existing manual policies remain compatible.

## Commands and storage

- `tracemantle manifest BUNDLE --format json` computes a canonical manifest from actual files. `--output PATH` is optional and must be outside the bundle.
- `tracemantle import-evidence EXPORT --bundle BUNDLE --bindings BINDINGS --store STORE --format json` parses the selected data format and writes its original bytes under `STORE/sources/` and normalized records under `STORE/records/`. `--input-format neutral` accepts evaluator-neutral JSON. `--adapter PATH` selects a user-supplied adapter file in place of the built-in Promptfoo one (see the adapter contract below). Omitting bindings preserves the source and reports unknown identities. Import returns exit 4 because import itself does not establish trusted behavioral evidence.
- `tracemantle compare BASELINE CANDIDATE --trusted-root REPOSITORY --base-revision FULL_COMMIT_SHA --evidence RECORD` reads both bundle directories, the trusted policy and supplied evidence. Repeat `--evidence` for additional records. `--require-observed-execution` additionally refuses to pass a required check on static analysis alone (see observed execution below). No files change unless `--output PATH` is explicitly selected.
- `tracemantle migrate-history LEDGER --store STORE` copies version-one history explicitly. Repeating the command is safe; originals are preserved and migrated records remain unknown for release comparison.

Stores must be outside evaluated bundles. Content-addressed files are published with a complete temporary write, fsync and exclusive hard-link creation. A matching object is reused only if its bytes are identical. Every new history record also has a unique run ID. No shared read/modify/write index is required, so concurrent writers preserve records.

## Promptfoo contract and provenance

The narrow adapter accepts **Promptfoo 0.118.10** and **0.124.1**, both with JSON results schema **3**. Other package versions or results schemas are rejected, not guessed. Its attributable source fixture is [sample-export.json at upstream commit c0b47e4](https://github.com/promptfoo/promptfoo/blob/c0b47e4a10b38a7a54c782b32fc779802dfaf72e/test/__fixtures__/sample-export.json), retained byte-for-byte with its MIT license under `tests/fixtures/upstream/promptfoo-0.118.10/`. The containing source checkout is tag 0.120.0; the actual export's `metadata.promptfooVersion` is 0.118.10. These are deliberately distinguished.

The additional [0.124.1 fixtures](../tests/fixtures/upstream/promptfoo-0.124.1/PROVENANCE.json)
were generated locally by the unmodified published npm package with its echo
provider and an explicitly deterministic error provider. They are authentic
package exports, not upstream-authored evaluation results: one pass, one assertion
failure, one provider error, no model calls. Original export bytes, reproduction
configs, provider, npm integrity and upstream MIT license are retained. The exact
release source is [421e795](https://github.com/promptfoo/promptfoo/tree/421e7959642c5d4cc1c983259a268de1c6f847b9).
The inspected contracts are `src/util/output.ts`, `src/models/evalResult.ts` and
`src/types/index.ts`/`src/types/shared.ts` in that revision.

For 0.124.1 the supported shape adds optional `vars`/`runtimeOptions` at the root
and `tokenUsage` in rows. `failureReason` is required: 0 with success means pass,
1 means assertion failure, 2 means infrastructure error; unsuccessful 0 remains
unknown. An aggregate grading pass must agree with `success`; it need not agree
with every component because threshold grading may pass partial results. Newer
trace, media, repeat-stability or other unverified shapes are rejected with a
pointer to the neutral route. This is an exact tested subset, not a broad version
range or all possible exports from either package.

The original 0.118.10 fixture has four riddle-evaluation results containing LLM rubric judgments. It proves parser compatibility with an authentic upstream format, not skill invocation or agent execution in this session. The importer marks such records `model-judgment`; generic exports without sufficient observation data remain `unknown`. It never infers `observed-execution` from a selected agent, provider label or user binding. A separate trusted runner can supply observed-execution records (see the external runner section below), but they must cross the same full-content trust boundary.

The export's providers, JavaScript/Python assertions, file references, extensions and environment settings are data. TraceMantle hashes or preserves them; it never imports or executes them. Source exports may contain evaluator data; keep their access controls appropriate. Normalized environment fields are limited to OS, Python, Node, network, sandbox and architecture, with no credential fields.

Bindings are a version-one JSON object with `schema_version: 1` and `rows`, mapping exact export result IDs to complete check-evidence objects. See the shipped [evidence schema](../src/tracemantle/schemas/evidence-v1.json) and `evidence_from_dict` for structural and cross-field checks. The adapter replaces artifact/configuration/fixture digests, observation time, result state, reason, adapter/runner/model and observation method with values derived from the export. A binding cannot override them. It verifies the bound bundle and resource digests against the actual supplied directory. Unsupported or unavailable identity produces an explicit error or unknown result. Present `gradingResult.componentResults` values must be arrays of objects; present component assertions must be objects and assertion types must be strings. Validation runs even for unbound rows. Null/scalar component arrays and invalid assertions produce an infrastructure-error envelope (exit 2), with no partially imported store.

## Adapter contract and external adapters

An adapter turns one export into canonical records. The built-in Promptfoo adapter and any external one implement the same function, documented in [`tracemantle.adapters`](../src/tracemantle/adapters/__init__.py):

```python
def adapt(export_bytes: bytes, bindings: dict) -> list[CheckEvidence]
```

`export_bytes` is the original export, bounded to 5 MiB. `bindings` is the decoded `--bindings` JSON object, or `{"schema_version": 1, "rows": {}}` when none is supplied; an external adapter defines its own meaning for the contents. The function returns records built with `tracemantle.adapters.evidence_from_dict` or raises `EvidenceError`. There is no partial result.

`import-evidence --adapter PATH` loads a Python file implementing that function instead of the built-in adapter. Without the flag nothing external is loaded and Promptfoo imports behave exactly as before. With it:

- The file is read once (1 MiB limit) and those bytes are what runs. This is ordinary Python executing with your privileges and no sandbox. Treat an adapter as trusted tooling: take it from the trusted checkout in CI, never from a candidate revision. A path inside the evaluated bundle is refused before any code runs.
- Each returned record is revalidated. `adapter` is replaced with `external/sha256:<digest of the adapter file>` and `artifact_sha256` with the digest of the export, so an adapter cannot claim the built-in identity or a different source. A trusted check can pin one exact adapter file with `context = { adapter = "external/sha256:..." }`.
- Records must still match the supplied bundle and its file digests, the original export is still preserved under `STORE/sources/`, and the import still exits 4. A failing adapter, a missing `adapt` function or a non-record return value is an infrastructure-error (exit 2) with no store written.

An external adapter can set any `observation_method`, including `observed-execution`. That is a claim by whoever ran the adapter, not something TraceMantle observed; it carries weight only after manual digest approval or a verified approval from explicitly authorized automation. Neither importing nor naming an observer establishes that an execution occurred.

## Canonical evidence fields

Every version-one `check-evidence` record binds:

| Fields | Meaning |
|---|---|
| `check_id`, `state` | Trusted check identity and pass/fail/unknown/skipped/infrastructure-error outcome |
| `bundle_sha256`, `inputs` | Full bundle identity and a path-to-SHA256 map of declared input content |
| `configuration_sha256`, `profile_sha256`, `checker_sha256`, `fixture_sha256` | Configuration, profile, checker and test-case identities |
| `artifact_sha256` | Full SHA-256 of preserved source export bytes |
| `observed_at`, `observation_method` | Time with timezone, and static-analysis/observed-execution/inferred-trace/model-judgment/unknown |
| `runner`, `adapter`, `model`, `model_revision`, `model_immutable` | Explicit execution identities; an alias is not an immutable revision |
| `permissions`, `environment`, `tokenizer` | Execution permissions, relevant nonsecret assumptions and counting provenance |
| `reason` | Reported explanation, escaped only at display boundaries |

No booleans are coerced from strings or numbers. Input digests are full lowercase SHA-256 values. Malformed, mismatched or incomplete records cannot produce a trusted pass. Duplicate JSON fields, excessive depth, explicit nonfinite constants and numeric exponent overflow are rejected through the shared bounded decoder. Validation covers the entire export, including values associated with unbound rows, before hashing or storing any source/record. Rejected imports return infrastructure-error (exit 2) with the normal JSON envelope when requested; finite numeric serialization and digests are unchanged.

## Trusted policy

Use `[tool.tracemantle.release]` in a TOML file committed to the trusted repository, normally `pyproject.toml`. Comparison reads that exact Git object. `--policy-relative` can select another tracked TOML config in the same base revision. The policy contains `schema_version = 1`, `trusted_evidence` (approved full canonical record digests) and an array of checks. `required_signers` is the only optional key in schema 1. Schema 2 additionally permits the explicit `automation` authority described below; unknown keys and unsupported versions fail closed.

Each check declares exactly `id`, `kind` (`static`, `behavioral`, `routing`), `inputs`, `coverage_complete`, `checker_path`, `checker_sha256`, `configuration_sha256`, `fixture_sha256`, `profile_sha256`, `max_age_seconds`, `required`, `context`, and `routing_neighbors`. The checker path must exist in the trusted base and its actual bytes must match the declared SHA-256. Checkers are identified, not executed by comparison. Inputs and routing-neighbor paths are normalized relative paths. Context may bind runner, adapter, model/revision, permissions, tokenizer digest, OS, Python, Node, network, sandbox and architecture.

The trust boundary is an explicit content allowlist committed by the trusted policy owner. `trusted_evidence` approves the **entire canonical evidence record**, including bundle, inputs, outcome and execution conditions; it is not an allowlist of runner names or artifact names. A candidate cannot take an authentic export and attach it to another bundle, alter the outcome or promote a model judgment without changing the digest. TraceMantle verifies that digest against the immutable trusted base. For this original manual route, the owner or trusted automation reviews a record and commits its digest to the trusted policy before it is accepted. Signer strings and attestations claimed inside a record are never read as proof; record signatures use the opt-in check below, and automation approvals use the separately scoped keys described later. Both take their authority from the trusted base.

### Optional signatures: `required_signers`

Record signatures are an additional, opt-in control. In schema 1 (and schema 2 without automation), a signed record whose digest is not in `trusted_evidence` is still rejected. Schema-2 automation uses a separately signed approval envelope; `required_signers` still requires a record signature in addition to that approval.

```toml
[tool.tracemantle.release]
schema_version = 1
trusted_evidence = ["<record sha256>"]
required_signers = [
  "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... release-owner",
  "RWQ...56-character minisign public key...",
]
```

When `required_signers` is present (1 to 100 keys), a record is accepted only if a valid signature from one of those keys is attached. When it is absent, record signature sidecars are not read; automation approval sidecars are a separate schema-2 opt-in. An empty list is a policy error, not a way to disable the check.

The signature is a sidecar next to the file passed to `--evidence`, so the version-one evidence schema has no new field and record digests do not change:

| Tool | Sidecar | Sign | Verified with |
|---|---|---|---|
| OpenSSH 8.1 or later | `RECORD.json.sig` | `ssh-keygen -Y sign -f KEY -n tracemantle-evidence RECORD.json` | `ssh-keygen -Y verify` |
| minisign | `RECORD.json.minisig` | `minisign -S -s KEY -m RECORD.json` | `minisign -V` |

The signed message is the record's canonical JSON bytes. Files written by `import-evidence` under `STORE/records/` are already canonical, so sign those files directly. A reformatted copy has the same record digest but different bytes; sign the canonical file and keep its sidecar next to whichever copy is compared. SSH signatures must use the namespace `tracemantle-evidence`; a signature made for `git` or `file` is rejected.

A missing sidecar, a signature by an unlisted key, a wrong namespace or a signature over other bytes leaves the check unknown (exit 4) with a reason naming the signature requirement. If a sidecar is present and the needed tool is not installed, comparison stops with infrastructure-error (exit 2). TraceMantle adds no cryptography dependency; it runs the system `ssh-keygen` or `minisign`. A signature shows that a key holder signed those bytes. It does not show that the recorded execution happened.

Candidate policy files and checker changes never replace the selected trusted policy. The [comparison workflow](../.github/workflows/compare.yml) checks out trusted and candidate revisions separately, installs only trusted code and grants read-only repository permissions. Its `policy_relative` and `evidence_directory` inputs default to `pyproject.toml` and `evidence/records`; the policy is still read from the selected immutable base, and records remain candidate-supplied data. Configure repository protections so the base SHA and workflow are selected by trusted maintainers. Running a candidate-supplied executable as the checker before this boundary would defeat it.

## Conservative invalidation

Comparison explains changed files, affected check IDs, rejected evidence and required reruns. Changed declared inputs and their Markdown dependency closure invalidate old results. A check declaring only `SKILL.md` therefore requires a rerun when a linked helper changes, including links following an escaped backtick, after a Setext heading or inside supported nested lists. Standalone code examples remain excluded. Unsupported container contexts propagate incomplete coverage through transitive Markdown dependencies and the manifest; they cannot authorize a passing gate. See [parsing boundaries](contracts.md). Description changes invalidate routing checks, with declared neighboring inputs also participating. Checker, profile, fixture or configuration identity changes invalidate governed evidence. If either bundle's dependency identity or a check's declared coverage is incomplete, reuse across a bundle change is refused and the full relevant suite must run.

Static reuse requires matching declared input digests and compatible checker/configuration identities. Behavioral reuse additionally requires observed execution, compatible context, freshness and an immutable model revision. Hosted aliases are not immutable versions. Every supplied record is historical evidence reuse; neither equal bundle hashes nor a trusted digest establishes fresh execution. There is no separate fresh-execution eligibility path. Runner, adapter, model and model revision, and every supplied environment/tokenizer value, must be nonblank and must not be `unknown` (ignoring surrounding whitespace and case). Environment and tokenizer mappings must be nonempty. These checks apply even if trusted context declares only permissions. The equal-bundle and nested-context corrections are included in 1.6.1. Required skipped checks become unknown. Conflicting approved records cannot be hidden by selecting a passing row: fail, infrastructure-error, unknown and skipped take precedence over pass. A policy with no required checks cannot establish release success.

Comparison exit codes: pass `0`, fail `1`, infrastructure-error `2`, unknown `4`, skipped `5`. Only pass permits release. Unknown means the evidence does not establish the gate, not that the skill definitively failed.

## Observed execution from an external runner

TraceMantle does not run skills, agents or evaluators. Observed-execution evidence comes from a runner you operate outside the package. Three pieces are provided as documentation, none of them imported by TraceMantle:

- [`observed-execution-v1.json`](schemas/observed-execution-v1.json): the versioned record a runner writes. Required fields are `schema_version`, `kind`, `check_id`, `outcome`, `observation_method` (must be `observed-execution`), `observed_at`, `bundle_sha256`, `inputs_sha256` (path to digest), `checker_sha256`, `configuration_sha256`, `fixture_sha256`, `profile_sha256`, `artifact_sha256` (digest of the captured transcript), `context` (runner, model, model revision and immutability, permissions, environment, tokenizer) and `reason`.
- [`observed_execution_runner.py`](examples/observed_execution_runner.py): a reference runner. It takes the bundle manifest from `tracemantle manifest`, pipes the fixture to your agent command, captures stdout, stderr and the exit code into a transcript, runs your checker script on that transcript (exit 0 pass, 1 fail, anything else infrastructure-error) and writes the record. If the bundle changes during the run or the command cannot start, the outcome is infrastructure-error.
- [`observed_execution_adapter.py`](examples/observed_execution_adapter.py): an adapter for `import-evidence --adapter` that converts the record into canonical check evidence. The canonical `artifact_sha256` is the digest of the runner record, which itself commits to the transcript digest.

The runner executes the command you pass with your privileges. Model revision, tokenizer, sandbox and network state are the operator's declarations; the runner cannot observe them. Copy both example files into trusted tooling and adapt them. A trusted check can pin the exact runner and adapter files through `context.runner` and `context.adapter`, since both identities contain the file's SHA-256.

`compare --require-observed-execution` (off by default) treats a required check as unknown (exit 4) unless an accepted record for it has observation method `observed-execution`. Accepted means approved by the selected policy and compatible with the check, as for any other record. Behavioral and routing checks already require observed execution, so the flag changes the result only for required `static` checks: evidence that passes without the flag becomes unknown with it. A fail or infrastructure-error stays as it is, optional checks are unaffected, and without the flag static-only workflows behave exactly as before.

Under the original manual route, a fresh run does not pass the gate by itself. Its new digest must be committed to the trusted base. The loop is: run, import, review the record (and sign it if the policy lists `required_signers`), commit its digest to `trusted_evidence` on the trusted branch, then compare against that base.

```yaml
- name: Observe the skill, then gate on approved observed execution
  shell: bash
  env:
    BASE_REVISION: ${{ inputs.base_revision }}
    BUNDLE: skills/my-skill
  run: |
    set -euo pipefail
    # 1. External runner: executes the pinned agent command outside TraceMantle.
    python trusted/tools/observed_execution_runner.py \
      --bundle "candidate/$BUNDLE" --check-id invoke --output-dir "$RUNNER_TEMP/observed" \
      --checker trusted/checks/invoke.py --configuration trusted/checks/agent-config.json \
      --fixture trusted/checks/invoke-prompt.txt --profile trusted/checks/profile.json \
      --model my-local-model --model-revision "sha256:<weights digest>" --model-immutable \
      --tokenizer my-tokenizer-v1 --sandbox container \
      -- my-agent-cli --skill "candidate/$BUNDLE"
    # 2. Import through the trusted adapter. Exit 4 is expected: imported claims are not yet approved.
    tracemantle import-evidence "$RUNNER_TEMP/observed/invoke.observed.json" \
      --adapter trusted/tools/observed_execution_adapter.py \
      --bundle "candidate/$BUNDLE" --store "$RUNNER_TEMP/store" || [ "$?" -eq 4 ]
    # 3. Gate on records whose digests the trusted base already approves.
    args=()
    while IFS= read -r -d '' record; do args+=(--evidence "$record"); done \
      < <(find candidate/evidence/records -maxdepth 1 -type f -name '*.json' -print0)
    tracemantle compare "trusted/$BUNDLE" "candidate/$BUNDLE" \
      --trusted-root trusted --base-revision "$BASE_REVISION" \
      --require-observed-execution --format github "${args[@]}"
```

Upload `$RUNNER_TEMP/store/records/` as a workflow artifact so the policy owner can review the new record and approve its digest. Check out `trusted` and `candidate` as in the [comparison workflow](../.github/workflows/compare.yml), and take the runner, adapter, checker and fixture from the trusted checkout. The tests for this path use a one-line Python command in place of an agent; no live agent or model was run against these examples.

## Executed examples and remaining empirical boundary

```bash
python -m pytest tests/test_build_plan_product.py -q
python -m pytest tests/test_build_plan_product.py::test_cli_trusted_base_cannot_be_weakened_by_candidate -q
tracemantle import-evidence tests/fixtures/upstream/promptfoo-0.118.10/sample-export.json \
  --bundle skills/tracemantle --store /tmp/tracemantle-import-example --format json
```

The tests create isolated local repositories and synthetic records for valid controls, helper-only changes, routing changes, incompatible/missing evidence and trusted-base tampering. Synthetic records are labeled as such. The final example is expected to exit 4 with unknown identities while preserving the authentic export. No live skill-evaluation runtime was supplied or invoked. Live behavioral performance remains unverified. Remote CI is tracked separately in [implementation status](implementation-status.md); local product tests do not establish remote results.

The authored [workflow controls](../tests/fixtures/ci-gates/README.md) provide a static pass, missing-evidence case and a helper-change candidate with policy/checker tampering for manual remote acceptance. The fixture README pins the original trusted control revision; the current candidate deliberately cannot satisfy it. The separate `verify-gates.yml` workflow deliberately fails a quality job and verifies that its dependent nonpublishing sentinel is skipped. It has read-only permissions and no publish step, environment or tag trigger. This tests failed-prerequisite behavior without enabling Release or uploading artifacts. See the [post-release audit record](verification/audit-1.6.1/acceptance.md) for executed runs and remaining live-evaluation limits.

Version 1.6.1 includes the Setext-heading, escaped-backtick, list-continuation and numeric-overflow corrections. [Patch verification](verification/release-1.6.1/acceptance.md) records the new heading and adjacent-block controls. [Current regression evidence](verification/audit-1.6.1/acceptance.md#dependency-and-numeric-boundary-corrections) uses synthetic approved records in temporary trusted Git repositories and mutations of the attributable Promptfoo export. No skill or evaluator was executed.

## Import evaluator-neutral JSON

Use `--input-format neutral` for data exported by any evaluator. The envelope is
`{"schema_version": 1, "records": [...]}`; each entry is a complete
[check-evidence-v1 object](../src/tracemantle/schemas/evidence-v1.json). No bindings
or executable adapter are needed. Unknown observations and identities must remain
explicit `unknown` values, never invented revisions or execution claims.

This complete [exporter example](examples/export_validation.py) runs real local
static validation through the Python API and emits the envelope. With the built
package installed and an absolute path to the owner-reviewed examples:

```bash
python -I "$EXAMPLES/export_validation.py" hello > result.json
tracemantle import-evidence result.json --input-format neutral --bundle hello --store evidence --format json
```

The import returns **4**, with state `unknown`: it stores the result but does not
approve it. The example produces static analysis, not agent execution. External
evaluators can emit the same full schema with their actual outcomes and identity.
All source fields are validated before the importer assigns
`adapter = tracemantle/neutral-v1` and `artifact_sha256 = SHA256(original export)`.
The source copy retains the original artifact reference. Complete source decoding
rejects duplicate keys, overflow, excessive depth/size and malformed records before
any store writes. Bundle and input hashes must match real supplied files.
Imported strings, commands and observation labels are data and are never executed.
Custom Python adapters remain available only for trusted code; use them from the
trusted tooling checkout in CI, with the caller's privileges understood.

## Protected automation

Read the [design and baseline checklist](automation-design.md) before deployment.
An owner initially commits policy schema 2 with scoped authority:

```toml
[tool.tracemantle.release]
schema_version = 2
trusted_evidence = []
# Existing checks and optional required_signers retain their contracts.
[tool.tracemantle.release.automation]
signers = ["ssh-ed25519 <actual public key>"]
checks = ["greeting"]
max_age_seconds = 3600
```

Use an actual OpenSSH public key or minisign public-key string. Keys approve only
listed check IDs; every check must exist in the same trusted policy. Required
check definitions, checker bytes, configuration/profile/fixture digests and context
remain governed by the immutable base. The comparison command never runs them.
The installed package, adapter and producer must also come from approved tooling;
Git identity checking cannot protect a candidate-replaced Python installation.

An approval sidecar is `RECORD.json.approval.json`, signed as
`RECORD.json.approval.json.sig` or `.minisig` using the existing
`tracemantle-evidence` OpenSSH namespace. Sign its canonical JSON bytes. The
`approval_envelope` helper constructs exactly these fields:

| Field | Binding |
| --- | --- |
| `schema_version`, `kind` | `1`, `automation-approval` |
| `evidence_sha256` | Entire canonical record, including outcome, inputs and execution context |
| `policy_sha256`, `trusted_revision` | Exact policy file and selected immutable trusted commit |
| `check_id`, `bundle_sha256` | Intended check and full candidate bundle |
| `run_id`, `run_started_at` | Unique protected scheduler run and timezone-qualified start |
| `issued_at`, `expires_at` | Approval issue/expiry timestamps with timezone |

Comparison requires independently supplied `--approval-run-id` and
`--approval-run-started-at`. Never read these flags from the candidate or its
artifacts. Evidence must have been observed between that start and issue time;
issue time cannot be in the future, and comparison must precede expiration.
Expiration minus run start cannot exceed the policy lifetime (1–86400 seconds).
Wrong records, subjects, policies, keys and run contexts fail closed. Missing tools
or malformed sidecars return infrastructure-error (2); missing/unapproved evidence
remains unknown (4). There is no fallback to an unchecked signature.

Replay into a different run is rejected. Repeated verification inside the same
unexpired run is allowed; there is no consumption database. The protected scheduler
must never reuse a run ID/start pair. Revocation takes effect when the verifier
selects a new base that removes the key; selecting an old base retains that old
base's authority. Removing `automation` restores the digest allowlist. Schema 1
cannot enable automation, and `required_signers` never independently bypasses
digest approval. Existing policies require no migration; enabling schema 2 is an
explicit owner review of authority. Optional record signatures remain additional
requirements on both approval routes.

All historical compatibility restrictions still apply, including refusal to reuse
mutable model aliases. There is **no** current-run alias exception. Required
unknown/skipped/missing, incompatible or conflicting records cannot produce a pass.
Signing a candidate-supplied JSON record without observing and validating its
result does not implement this workflow.

### Runnable isolated producer and verifier

The [protected producer](examples/protected_automation.py) is a Linux mechanics
example, not a general evaluator. Prerequisites: the trusted built package,
Python 3.10+, Git, OpenSSH with `-Y`, bubblewrap with permitted user namespaces,
and `/usr/bin/python3` plus `prlimit`. The host, system runtime and operator-owned
workspace must be trusted and inaccessible to candidate processes. This example
has no network or model calls and does not claim to evaluate an agent.

One-time setup generates an example key and commits a scoped policy, runner,
checker, fixture, configuration and profile into a temporary trusted repository.
Use an empty destination. `$EXAMPLES` is an absolute path to the reviewed
`docs/examples` directory. Use the built-package virtual environment:

```bash
DEMO=/tmp/tracemantle-protected-example
BASE=$(python -I "$EXAMPLES/protected_automation.py" setup "$DEMO")
```

For the first candidate, change only its helper and supply protected run context:

```bash
printf 'print("hello")\n# candidate one\n' > "$DEMO/candidate/demo/helper.py"
RUN_ID=local-demo-1
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RECORD=$(python -I "$DEMO/trusted/producer.py" run "$DEMO" \
  --base-revision "$BASE" --run-id "$RUN_ID" --run-started-at "$START")
tracemantle compare "$DEMO/baseline/demo" "$DEMO/candidate/demo" \
  --trusted-root "$DEMO/trusted" --base-revision "$BASE" --evidence "$RECORD" \
  --approval-run-id "$RUN_ID" --approval-run-started-at "$START"
```

Comparison returns 0 and reports `greeting: pass`. The protected observer copies
and verifies the bundle, then starts a bubblewrap sandbox with only system runtime
files and the read-only bundle. It clears the environment, disables network,
limits output/CPU/time, and mounts no signing keys, host home or observer output.
Candidate helper execution ends before the trusted checker compares captured
stdout/exit status with the trusted fixture. The observer constructs the record
itself, imports through the built-in neutral adapter, validates compatibility,
then signs an approval. It accepts no uploaded record to sign. Records, original
exports and transcripts remain outside the evaluated bundle.

The signed record uses an explicitly deterministic stand-in identity, not a real
model. A failed checker produces no approval. Candidate policy, adapter or checker
files cannot replace the selected base files. The test also attempts to read a
host key path and inherited secret inside the sandbox; both are absent.

A production scheduler must select the base/run context outside candidate control,
use a protected immutable workflow and trusted installed toolchain, enforce sandbox
isolation, and secure the key. For multi-job evaluation, only an authenticated
trusted observer may transfer the bounded transcript to approval; a candidate job's
self-reported result is insufficient. Do not place signing credentials in an
evaluator job, install candidate packages in the signing job, or permit candidate
workflow edits to run with those credentials. This local example does not configure
repository protections or a hosted runner for you.

## Detect helper changes

Continue the isolated example above, keeping its original `$BASE` and policy:

```bash
printf 'print("hello")\n# candidate two\n' > "$DEMO/candidate/demo/helper.py"
tracemantle compare "$DEMO/baseline/demo" "$DEMO/candidate/demo" \
  --trusted-root "$DEMO/trusted" --base-revision "$BASE" --evidence "$RECORD" \
  --approval-run-id "$RUN_ID" --approval-run-started-at "$START"
```

The old approval returns **2**, `outside the trusted check or candidate bundle
scope`: the signed bundle is different. Manual historical reuse also invalidates
checks affected by direct or transitive helper changes, returning unknown and
required reruns; incomplete discovery never authorizes reuse across a changed
bundle. The existing trusted-Git dependency tests cover that separate reuse route.

Now run the changed candidate with new scheduler context and compare:

```bash
RUN_ID=local-demo-2
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RECORD=$(python -I "$DEMO/trusted/producer.py" run "$DEMO" \
  --base-revision "$BASE" --run-id "$RUN_ID" --run-started-at "$START")
tracemantle compare "$DEMO/baseline/demo" "$DEMO/candidate/demo" \
  --trusted-root "$DEMO/trusted" --base-revision "$BASE" --evidence "$RECORD" \
  --approval-run-id "$RUN_ID" --approval-run-started-at "$START"
```

This returns **0**, using the same policy and base commit. No evidence digest was
committed for either run. Run IDs shown here are local examples; deployment must
use unique scheduler IDs including retry/attempt identity.

Hashes identify content. Signatures identify an approving key holder. Execution
records depend on the trusted observer and its environment. None individually
establishes universal safety or correctness, and this deterministic example
establishes workflow mechanics only.

## Experimental closed check scopes (unreleased)

Schema 3 retains schema-2 approval controls and permits `input_scope_path` on a
`static` check or the new `deterministic` kind. The latter requires real
`observed-execution`, plus known runner, adapter, Python and OS context. It means
non-model maintenance execution, such as helper regression tests. Evidence must
set both model and model_revision to the literal `none`; naming a model prevents
reuse even with digest approval. It does not
satisfy a behavioral/routing check and does not relax model identity requirements.

The scope path names a JSON blob in the same selected trusted Git revision as
the policy and checker. Its SHA-256 must equal the check's `profile_sha256`, which
also binds every approved evidence record. Scope JSON contains exactly:

```json
{
  "schema_version": 1,
  "inputs": ["SKILL.md", "resources/helper.py"],
  "rationale": "Reviewed checker reads only these files; describe the actual review here.",
  "assumptions": ["Pin interpreter, tools, configuration and all external inputs in configuration_sha256/context."],
  "unresolved": []
}
```

Inputs must exactly equal the check's sorted normalized input set. Rationale and
assumptions must be nonempty, unresolved must be empty, and coverage_complete
must be true. These are **trusted assertions requiring review**, not proof inferred
from prose or one file-read trace. A boolean alone cannot opt into this contract.
An unresolved execution input requires running that check; do not issue a closed
scope for it. Changes to declaration bytes invalidate the profile and require
new evidence approval. Candidate scope/policy files never replace trusted blobs.

For this opt-in only, the reviewed set replaces inferred Markdown closure for
that check. An example in documentation need not be a test input; a command
extracted from that documentation must be. Include transitive helpers, fixtures,
configuration, executable identity, environment and loader assumptions. Bind
external inputs to the existing configuration/context fields and compare their
**current** identity before omitting execution. Comparison cannot observe a
runner's environment or verify a prose assertion. The SARIF integration checks
installed file hashes and refuses upstream-suite reuse on unreviewed new modules.

Manifest schema 2 distinguishes `resource_errors` from documentation uncertainty.
Closed scopes require schema-2 manifests with no resource errors on either side.
Broken explicit links, escapes, unreadable resources, cycles, symlinks and limits
cannot be excused by a declaration. Legacy manifests and policies still load;
legacy incomplete coverage remains conservative. Bundle content hashes and
schema-1 evidence identities are unchanged. Documentation uncertainty remains
visible in comparison issues, even when all required closed scopes pass.

A workflow may execute the required reruns and reuse independently passing checks;
that is not permission to treat an unknown release comparison as a passing release.
Always generate required current outputs. A maintenance pass does not supply a
new scan/report, and immutable identity does not prove arbitrary determinism.
See the [maintainer deployment](../integrations/sarif/README.md) for the bounded
reviewed scope and separate simple-cache comparison.
