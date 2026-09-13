# Bundle and release evidence workflow

TraceMantle separates content identity, analysis results and trust. A SHA-256 digest identifies bytes; it does not prove that those bytes are correct or that an execution occurred. The comparison gate uses only checks, checker bytes and approved evidence digests anchored to the selected trusted base commit.

## Commands and storage

- `tracemantle manifest BUNDLE --format json` computes a canonical manifest from actual files. `--output PATH` is optional and must be outside the bundle.
- `tracemantle import-evidence EXPORT --bundle BUNDLE --bindings BINDINGS --store STORE --format json` parses the pinned export and writes its original bytes under `STORE/sources/` and normalized records under `STORE/records/`. Omitting bindings preserves the source and reports unknown identities. Import returns exit 4 because import itself does not establish trusted behavioral evidence.
- `tracemantle compare BASELINE CANDIDATE --trusted-root REPOSITORY --base-revision FULL_COMMIT_SHA --evidence RECORD` reads both bundle directories, the trusted policy and supplied evidence. Repeat `--evidence` for additional records. No files change unless `--output PATH` is explicitly selected.
- `tracemantle migrate-history LEDGER --store STORE` copies version-one history explicitly. Repeating the command is safe; originals are preserved and migrated records remain unknown for release comparison.

Stores must be outside evaluated bundles. Content-addressed files are published with a complete temporary write, fsync and exclusive hard-link creation. A matching object is reused only if its bytes are identical. Every new history record also has a unique run ID. No shared read/modify/write index is required, so concurrent writers preserve records.

## Promptfoo contract and provenance

The narrow adapter accepts **Promptfoo 0.118.10**, JSON results schema **3**. Other versions are rejected, not guessed. Its attributable source fixture is [sample-export.json at upstream commit c0b47e4](https://github.com/promptfoo/promptfoo/blob/c0b47e4a10b38a7a54c782b32fc779802dfaf72e/test/__fixtures__/sample-export.json), retained byte-for-byte with its MIT license under `tests/fixtures/upstream/promptfoo-0.118.10/`. The containing source checkout is tag 0.120.0; the actual export's `metadata.promptfooVersion` is 0.118.10. These are deliberately distinguished.

The fixture has four riddle-evaluation results containing LLM rubric judgments. It proves parser compatibility with an authentic upstream format, not skill invocation or agent execution in this session. The importer marks such records `model-judgment`; generic exports without sufficient observation data remain `unknown`. It never infers `observed-execution` from a selected agent, provider label or user binding. A separate trusted runner can supply canonical observed-execution records, but they must cross the same full-content trust boundary.

The export's providers, JavaScript/Python assertions, file references, extensions and environment settings are data. TraceMantle hashes or preserves them; it never imports or executes them. Source exports may contain evaluator data; keep their access controls appropriate. Normalized environment fields are limited to OS, Python, Node, network, sandbox and architecture, with no credential fields.

Bindings are a version-one JSON object with `schema_version: 1` and `rows`, mapping exact export result IDs to complete check-evidence objects. See the shipped [evidence schema](../src/tracemantle/schemas/evidence-v1.json) and `evidence_from_dict` for structural and cross-field checks. The adapter replaces artifact/configuration/fixture digests, observation time, result state, reason, adapter/runner/model and observation method with values derived from the export. A binding cannot override them. It verifies the bound bundle and resource digests against the actual supplied directory. Unsupported or unavailable identity produces an explicit error or unknown result. Present `gradingResult.componentResults` values must be arrays of objects; present component assertions must be objects and assertion types must be strings. Validation runs even for unbound rows. Null/scalar component arrays and invalid assertions produce an infrastructure-error envelope (exit 2), with no partially imported store.

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

No booleans are coerced from strings or numbers. Input digests are full lowercase SHA-256 values. Malformed, mismatched or incomplete records cannot produce a trusted pass. Duplicate JSON fields, excessive depth and nonfinite numeric constants are rejected.

## Trusted policy

Use `[tool.tracemantle.release]` in a TOML file committed to the trusted repository, normally `pyproject.toml`. Comparison reads that exact Git object. `--policy-relative` can select another tracked TOML config in the same base revision. The policy contains exactly `schema_version = 1`, `trusted_evidence` (approved full canonical record digests), and an array of checks.

Each check declares exactly `id`, `kind` (`static`, `behavioral`, `routing`), `inputs`, `coverage_complete`, `checker_path`, `checker_sha256`, `configuration_sha256`, `fixture_sha256`, `profile_sha256`, `max_age_seconds`, `required`, `context`, and `routing_neighbors`. The checker path must exist in the trusted base and its actual bytes must match the declared SHA-256. Checkers are identified, not executed by comparison. Inputs and routing-neighbor paths are normalized relative paths. Context may bind runner, adapter, model/revision, permissions, tokenizer digest, OS, Python, Node, network, sandbox and architecture.

The trust boundary is an explicit content allowlist committed by the trusted policy owner. `trusted_evidence` approves the **entire canonical evidence record**, including bundle, inputs, outcome and execution conditions; it is not an allowlist of runner names or artifact names. A candidate cannot take an authentic export and attach it to another bundle, alter the outcome or promote a model judgment without changing the digest. TraceMantle verifies that digest against the immutable trusted base. This initial trust policy requires the owner or trusted automation to review/verify a record and commit its digest to the trusted policy before it is accepted; it does not validate arbitrary external signatures or GitHub attestations by reading claimed signer strings.

Candidate policy files and checker changes never replace the selected trusted policy. The [comparison workflow](../.github/workflows/compare.yml) checks out trusted and candidate revisions separately, installs only trusted code and grants read-only repository permissions. Its `policy_relative` and `evidence_directory` inputs default to `pyproject.toml` and `evidence/records`; the policy is still read from the selected immutable base, and records remain candidate-supplied data. Configure repository protections so the base SHA and workflow are selected by trusted maintainers. Running a candidate-supplied executable as the checker before this boundary would defeat it.

## Conservative invalidation

Comparison explains changed files, affected check IDs, rejected evidence and required reruns. Changed declared inputs and their Markdown dependency closure invalidate old results. Description changes invalidate routing checks, with declared neighboring inputs also participating. Checker, profile, fixture or configuration identity changes invalidate governed evidence. If either bundle's dependency identity or a check's declared coverage is incomplete, reuse across a bundle change is refused and the full relevant suite must run.

Static reuse requires matching declared input digests and compatible checker/configuration identities. Behavioral reuse additionally requires observed execution, compatible context, freshness and an immutable model revision. Hosted aliases are not immutable versions. Every supplied record is historical evidence reuse; neither equal bundle hashes nor a trusted digest establishes fresh execution. There is no separate fresh-execution eligibility path. Runner, adapter, model and model revision, and every supplied environment/tokenizer value, must be nonblank and must not be `unknown` (ignoring surrounding whitespace and case). Environment and tokenizer mappings must be nonempty. These checks apply even if trusted context declares only permissions. The equal-bundle and nested-context corrections are unreleased after 1.6.0. Required skipped checks become unknown. Conflicting approved records cannot be hidden by selecting a passing row: fail, infrastructure-error, unknown and skipped take precedence over pass. A policy with no required checks cannot establish release success.

Comparison exit codes: pass `0`, fail `1`, infrastructure-error `2`, unknown `4`, skipped `5`. Only pass permits release. Unknown means the evidence does not establish the gate, not that the skill definitively failed.

## Executed examples and remaining empirical boundary

```bash
python -m pytest tests/test_build_plan_product.py -q
python -m pytest tests/test_build_plan_product.py::test_cli_trusted_base_cannot_be_weakened_by_candidate -q
tracemantle import-evidence tests/fixtures/upstream/promptfoo-0.118.10/sample-export.json \
  --bundle skills/tracemantle --store /tmp/tracemantle-import-example --format json
```

The tests create isolated local repositories and synthetic records for valid controls, helper-only changes, routing changes, incompatible/missing evidence and trusted-base tampering. Synthetic records are labeled as such. The final example is expected to exit 4 with unknown identities while preserving the authentic export. No live skill-evaluation runtime was supplied or invoked. Live behavioral performance remains unverified. Remote CI is tracked separately in [implementation status](implementation-status.md); local product tests do not establish remote results.

The authored [workflow controls](../tests/fixtures/ci-gates/README.md) provide a static pass and missing-evidence case for manual remote acceptance. The separate `verify-gates.yml` workflow deliberately fails a quality job and verifies that its dependent nonpublishing sentinel is skipped. It has read-only permissions and no publish step, environment or tag trigger. This tests failed-prerequisite behavior without enabling Release or uploading artifacts. See the [post-release audit record](verification/audit-1.6.1/acceptance.md) for executed runs and remaining live-evaluation limits.
