# TraceMantle implementation status

Operative plan: [original DOCX](SkillCheck_Technical_Debt_and_Product_Plan.docx), preserved under its original filename. Baseline commit: `b540a3f047bf411170e8cb95bbe630ca7bf96c14`, version 1.5.0. Candidate: **TraceMantle 1.6.0**, unpublished. Implementation, local acceptance and full remote CI are complete for the implementation commit recorded below. Artifacts were built and verified without publishing.

The complete plan, including both tables, was read before implementation. Instruction discovery covered ancestors, hidden directories, scoped instructions and case variants; `.github/CLAUDE.md` was the only repository instruction file. Contributor guidance, build workflows and historical remediation were also read. The supplied DOCX and unrelated local files were preserved. Those implementation-stage results predate the owner's repository rename; post-rename work is recorded below. No package publication, release or deployment was performed.

## Requirement ledger

| ID | Result | Implementation and executed acceptance |
|---|---|---|
| R01 | Implemented, locally verified | Canonical package/CLI, deprecated public import wrappers, legacy-to-canonical per-field TOML precedence, explicit migration. Clean wheel/source and old-uninstall/new-install checks in `scripts/verify_artifacts.py`; [migration](migration.md), [owner checklist](rename-checklist.md), [old-name audit](verification/name-audit.md). |
| D01 | Implemented, locally verified | Standard fields separated from vendor/ecosystem advice. Pinned skills-ref 0.1.0 at `69ef37e…`; 13 shared cases: 10 agreements and 3 documented naming/spec divergences. [Conformance](verification/conformance.json), [profiles](profiles.md), retained source/license/digests. |
| D02 | Implemented, locally verified | Line-based delimiters, BOM/CRLF policy, duplicate/non-string key rejection, immutable YAML and full-file spans. Malformed and valid controls in `test_build_plan_core.py`, parser and YAML suites. |
| D03 | Implemented, locally verified | Actual byte-limit-plus-one reads; YAML depth, nodes, aliases and expanded-structure caps; bounded JSON, source batches, dependency traversal, graphs and history. Real-process adversarial tests in `test_build_plan_acceptance.py`; [contracts](contracts.md). |
| D04 | Implemented, locally verified | Explicit default heuristic and optional tiktoken with provenance, ordinary special-token literals, cold-offline error and explicit working fallback. Both interpreter suites plus held-out tiktoken calibration executed. |
| D05 | Implemented, locally verified | C0/C1 escaping at terminal/Markdown/agent/annotation boundaries; reversible JSON. Source/ingest/formatter/history and no-color regressions pass. |
| D06 | Implemented, locally verified | Conditional tomli on 3.10, stdlib tomllib on 3.12, immutable per-root settings, explicit default CLI values, canonical alias precedence and ambiguity rejection. Both interpreter suites pass. |
| D07 | Implemented, locally verified | Merge/filter/final gate after all diagnostics, resolved input deduplication, full-file graph locations, per-file results and one JSON envelope across advertised report modes. Malformed batch emit cases continue independently. |
| D08 | Implemented, locally verified | Strict v1 reader and immutable full-digest per-run records outside bundles; final history policy, bounded reads, preserved originals and idempotent migration. Eight simultaneous real writers preserve every record; malformed history cannot establish a gate pass. |
| D09 | Implemented, locally verified | Shared Markdown tokenization and direct/transitive resource identity, fence handling, deterministic missing/escape/cycle diagnostics, conservative unknowns. Cross-branch cycles and actual chain depth have dedicated regressions. |
| D10 | Implemented, locally verified | Frozen shared source model reused by validation, graph, scoring, rendering and history. Real CLI cProfile test observes exactly one source parse. Graph/report workload improves 49.8% at 1,000 skills. |
| D11 | Implemented, locally verified | Strict versioned evidence binds all identities/context; original imports preserved; observation methods separated. Entire canonical evidence digests must be approved by the immutable trusted base. Mismatches, stale/incomplete context and self-reported claims remain unknown. |
| D12 | Implemented, locally and remotely verified | Shared full quality workflow gates exact retained wheel/source artifacts; constraints preserve consumer dependency ranges; optional tokenizer job; existing attestations/trusted publishing retained behind new-distribution safeguards. Clean installed artifact verification passes; [pre-rename local digests](verification/artifacts.json), [remote CI and artifact digests](verification/remote-ci.json). |
| D13 | Implemented, locally verified | Corrected skills-ref CLI/dirname claims and historical labels; generated CLI/config/rule references pass freshness checks; versioned vendor registry explicitly marks untested runtime applicability. |
| D14 | Implemented, locally verified | Eight separately authored, MIT-licensed held-out texts span prose languages, code and size. Unchanged heuristic measured separately: 37.4% median token error; 24 budget decisions = 11 TP, 12 TN, 0 FP, 1 FN; eight semantic abstentions. [Calibration](verification/calibration-v1.json). No trigger/task-success claim. |
| P01 | Implemented, locally verified | Canonical whole-bundle manifests include original bytes, full SHA-256, normalized paths, sizes and executable modes; ambiguous paths rejected, symlinks/incomplete dependencies explicit. Helper-only changes alter identity. |
| P02 | Implemented, locally verified | Narrow Promptfoo 0.118.10/results-v3 adapter tested with byte-exact attributable upstream export and license. Four authentic riddle rubric results are model judgments, not skill execution. Strict bindings, source preservation and data-only parsing verified. |
| P03 | Implemented, locally verified | Conservative five-state comparison, freshness/context/coverage checks, governed input and routing invalidation, missing-evidence blocking, alias reuse refusal, conflicting-record policy and required-rerun reasons. Twenty initial scenario fixtures plus hardening tests. |
| P04 | Implemented, locally verified; remote workflow unexecuted | Integrated manifest/import/compare/migrate commands render one analysis as text, JSON or GitHub annotations. Real temporary-Git end-to-end tests show candidate policy cannot weaken the selected base/checker. Trusted comparison workflow installs only trusted code. |

## Executed verification

- Baseline: **1,056 passed, 2 skipped**, 90.37% coverage. The two baseline skips were missing PATH access to pre-commit. Baseline Ruff and strict mypy passed; exact old wheel/source built before edits.
- Final CPython 3.10.14: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q --cov-fail-under=80`: **1,168 passed**, **87.78%** coverage. Pre-commit integration ran. [Log](verification/tests-python310.txt).
- Final CPython 3.12 with `[dev,tiktoken]` and constrained dependencies: **1,164 passed, 4 skipped**, **87.57%** coverage. The four pre-existing skips target the 3.10-only TOML fallback; those tests ran on 3.10. [Log](verification/tests-python312-tokenizer.txt).
- `ruff check src tests scripts`, strict `mypy` (**73 source files**), `scripts/generate_reference.py --check` and `git diff --check`: passed. No gate was lowered.
- `scripts/verify_reference_corpus.py`: passed on supported reference runtime CPython 3.12. `scripts/calibrate_advisories.py`: passed with tiktoken 0.14.0.
- Self-host symbolic and graph validation: exit 0, with advisory/unverified metadata clearly labeled. [JSON](verification/self-host.json). `scripts/check_changelog_release.py v1.6.0`: passed.
- `python -m build --no-isolation --outdir candidate-dist` and `scripts/verify_artifacts.py candidate-dist --legacy-wheel …/skillcheck-1.5.0-py3-none-any.whl`: clean wheel/source installs, canonical executable/module, supported deprecated imports, schemas, py.typed, graph/manifest acceptance and `pip check` passed. Pre-rename candidate artifact hashes are in the linked verification report; later builds have their own digests.
- Forty focused initial fixtures (20 source, 20 scenario) plus eight held-out sources retain explicit MIT redistribution terms. Pinned upstream corpora retain their own licenses and provenance. Synthetic evidence is never presented as a real execution.

## Performance and decisions

[Full measurements and variability](verification/performance.md) document fresh-process CLI and warm batches at 1/100/1,000 sources, reference/import/history stress and peak allocations. At 1,000 sources, graph/report improves **49.8%**, warm validation improves **3.0%**, and cold CLI grows **8.0%**. Peak traced Python memory grows **3.3%**. Small CLI startup, transitive-reference inspection and strict legacy-history reads exceed the relative 10% target with explicit correctness justifications and absolute timings. The corpus and measurement limits are stated; no production-wide guarantee is implied.

New history stores are immutable and external to bundles. Legacy history stays read-compatible and migration remains an explicit copy. New reports use explicit envelope/content versions; stable v1 identifiers keep their meaning. Python import compatibility requires uninstalling this project's old distribution first because both packages otherwise own overlapping paths. The default new installation provides no old executable.

## Post-rename verification

The owner renamed the repository to `moonrunnerkc/tracemantle`. On 2026-09-12, the new GitHub URL returned HTTP 200 and the old URL redirected with HTTP 301. Active repository/package/integration links and existing CI/license badges now use the new name. The local HTTPS remote is `https://github.com/moonrunnerkc/tracemantle.git`. Historical identifiers and the original DOCX filename remain unchanged.

GitHub account `moonrunnerkc` has admin access. `main` has no branch protection and there are no repository rulesets, so direct pushes do not bypass protections. The `pypi` environment has no required reviewers, wait timer or ref restrictions, and allows administrator bypass. These protections were reviewed without changing them. The repository's default workflow token is read-only; workflow PR approvals are disabled.

Publishing is explicitly disabled in two places: `TRACEMANTLE_PUBLISH_ENABLED=false` and Release workflow state `disabled_manually`. Existing release tags and release-note automation remain intact. The publish job requires the reused full quality workflow; moving the major tag requires successful publishing. No release workflow or deployment was invoked.

Post-rename local acceptance passed in clean constrained environments:

- CPython 3.10.14: `make verify-release`, **1,168 passed**, **87.67% coverage**. Ruff, strict mypy (73 source files), self-host symbolic/graph checks, wheel/source builds and clean installs passed. A separate `verify_artifacts.py --legacy-wheel` run passed old-uninstall/new-install migration for both artifacts.
- CPython 3.12 with the optional tokenizer: **1,164 passed, 4 expected version-specific skips**, **87.57% coverage**. Calibration and the pinned reference-conformance script passed.
- Generated-reference freshness, changelog gate, local documentation links, staged diff whitespace and original DOCX byte preservation passed. Tests now recognize Windows profiler paths; Git attributes preserve source/fixture bytes across platforms and retain the intentional CRLF control.

The original local `.venv` contains stale pre-rename executable paths and was preserved. Verification used `/tmp/tracemantle-post-rename-310` and `/tmp/tracemantle-py312`; recreate a moved checkout's virtual environment before using its console scripts.

Implementation commit `bd62f5dedb70ead010f921d1d94c63502581cfc6` was pushed directly to `main`. [Initial remote CI](https://github.com/moonrunnerkc/tracemantle/actions/runs/34725943611) completed: all 12 OS/Python test cells and the tokenizer job passed. Strict typing failed because Python 3.12 did not install the Python 3.10 `tomli` runtime dependency; the dependent packaging job correctly skipped.

The fix includes `tomli` in development extras because mypy targets Python 3.10 regardless of its host interpreter. Fresh Python 3.12 strict typing, Ruff, generated docs, rebuilt wheel/source and both clean artifact installs passed. [Corrected remote CI](https://github.com/moonrunnerkc/tracemantle/actions/runs/34726120556) completed successfully on `fe7faa37f446dc817b292e3a2e103775a62e6a0f`: **15 of 15 jobs passed**, comprising all 12 Linux/macOS/Windows × Python 3.10/3.11/3.12/3.13 cells, Ruff/generated docs/strict typing, optional tokenizer/calibration/conformance, and packaging with clean wheel/source installs. The unchanged 80% coverage gate passed throughout. The remote `tracemantle-dist` and separate `tracemantle-verification` artifacts were retained; the verification report was downloaded and checked. [Immutable run and artifact records](verification/remote-ci.json) distinguish this remote evidence from earlier local builds.

The completion documentation is a subsequent commit and triggers the same full [CI workflow on main](https://github.com/moonrunnerkc/tracemantle/actions/workflows/ci.yml?query=branch%3Amain). Handoff requires that exact final commit's run to complete successfully as well; the final SHA and run link are reported with the handoff. No earlier run is substituted for its checks.

## External prerequisites and completion boundary

PyPI account access is blocked: the browser runtime reports no available browser, and there is no PyPI account connector. Public `https://pypi.org/pypi/tracemantle/json` returned HTTP 404, which cannot confirm name availability, ownership or pending publishers. The owner must inspect/create/correct the new distribution's publisher to **moonrunnerkc / tracemantle / release.yml / pypi** in the owning PyPI account. [Exact owner checklist](rename-checklist.md) includes account links and the environment-policy review needed before any future publication.

The trusted comparison workflow, an actual failed remote release run, remote attestations and live agent/skill evaluation have not been executed. Their configuration and local tests do not establish live behavior. Live behavioral claims require an authorized runtime and actual observed evidence approved through the documented trust boundary. Publishing, release tags, public releases and deployment require a separate explicit instruction; both publishing safeguards must stay disabled until then.
