# Post-release implementation audit

Baseline: `0c18c10`, released TraceMantle 1.6.0. This audit covers unreleased fixes intended for the next patch, expected to be 1.6.1. The repository convention keeps package, self-host and latest changelog release versions coherent until release preparation. Local artifacts therefore still identify version 1.6.0; their source revision and hashes distinguish them from the immutable public release. No tag or published artifact is replaced.

Instruction discovery covered `/`, `/Users`, `/Users/brad`, `/Users/brad/projects`, the repository and hidden/relevant subdirectories, including all four requested filename variants. Only `.github/CLAUDE.md` applies within the repository, scoped to `.github`. The full original DOCX, including both tables, was extracted in document order and read. Its filename and bytes are unchanged. README, contributor guidance, contracts, evidence/migration/profile documentation, generated reference, historical remediation/verification, constraints, build targets, Action and all four existing workflows were reviewed. Historical release results are retained as historical evidence.

## Requirement checklist

The baseline classification records the investigation state, not a retrospective completion claim. Fresh acceptance below supplements the original ledger.

| ID | Baseline classification | Correction or verification and evidence |
|---|---|---|
| R01 | Already implemented; fresh install verification required | `pyproject.toml`, `src/skillcheck` wrappers, `config_loader.py`, `history_store.py`; `test_version_coherence.py`, `test_build_plan_core.py`, artifact migration procedure; [migration](../../migration.md). Released identity, attribution and tags preserved. |
| D01 | Already implemented; reverify | `rules/frontmatter_fields.py`, profile registry and pinned corpus; `test_build_plan_core.py`, `verify_reference_corpus.py`; [conformance](conformance.json), [profiles](../../profiles.md). |
| D02 | Already implemented; reverify | `parser.py` line boundaries, immutable YAML and source spans; parser/frontmatter/build-plan tests; [contracts](../../contracts.md). |
| D03 | Implemented with defective nested input paths | `promptfoo.py`, `config_loader.py`, `bundle.py`, `policy.py` now validate before access/hash. `test_audit_regressions.py` plus real bounded input, alias, graph and batch tests; [contracts](../../contracts.md). |
| D04 | Implemented; offline test defective | `test_cold_offline_tokenizer_is_explicit` clears proxy/cache inheritance and reserves a refused local port. Both optional-tokenizer and absent-tokenizer processes, including inherited lowercase bypass settings; tokenizer provenance unchanged. |
| D05 | Defective history error/warning paths | `commands.py::run_show_history` and adjacent ingest I/O diagnostic use terminal escaping. Tests cover missing, multiple, empty-store and removed-before-read paths, no-color, Unicode and reversible JSON; [contracts](../../contracts.md). |
| D06 | Implemented; automatic discovery defective | Reject non-table `tool` in `project_configs`; JSON config-error envelope in `cli.py`. Existing 3.10 `tomli` runtime and unconditional dev dependency retained. Config precedence, aliases and no-global-state regressions rerun on both interpreters. |
| D07 | Implemented; config/product error output incomplete | Schema-2 config error envelope and manifest error rendering in all product formats. Batch continuation, final strict/ignore policy, deduplication and full-file locations remain tested; [contracts](../../contracts.md). |
| D08 | Already implemented; reverify | Immutable `history_store.py` records, strict v1 reader, explicit migration; concurrent real writers and history policy tests. Null descriptions remain hashable for invalid-skill history; ordinary validation rejects them. |
| D09 | Defective code-context extraction | `markdown.py` masks equal-delimiter inline spans and indented blocks before all link/definition/HTML/directive extraction, retaining standalone resource paths. Unit and real CLI/manifest regressions cover locations and real dependencies; [contracts](../../contracts.md). |
| D10 | Already implemented; measure fixes | Parsed-document reuse preserved. cProfile tests assert one parse for graph/report/history and manifests. Five-repeat fresh baseline/current measurements cover planned workloads; historical 49.8% improvement is not claimed as newly reproduced. |
| D11 | Defective equal-bundle behavioral eligibility | `comparison.py` requires nonblank, known identity/context and immutable model identity for every historical behavioral record. Approved digests and equal hashes never establish freshness. API and real CLI regressions; [evidence workflow](../../evidence-workflow.md). |
| D12 | Implemented; failed-prerequisite execution unverified | Exact clean wheel/source installs and legacy migration, supported matrix, constraints and optional tokenizer retained. `verify-gates.yml` is an isolated manual negative acceptance path with a failing quality job and nonpublishing sentinel. No release guards changed. |
| D13 | Already implemented; affected documentation update required | Focused README, changelog, contracts, evidence workflow, migration and ledger corrections. Generated reference checked against code; historical records and DOCX preserved. |
| D14 | Already implemented; reverify | `calibrate_advisories.py`, eight licensed held-out sources; [calibration](calibration.json). Token error and budget outcomes remain separate from eight semantic abstentions; no trigger/task-success claim. |
| P01 | Implemented; description canonicalization defective | `bundle.py` rejects unsupported non-string/non-null descriptions before hashing. Full byte/mode/resource identity, helper changes, path rejection and parse reuse tests retained; [contracts](../../contracts.md). |
| P02 | Implemented; nested pinned export parsing defective | `promptfoo.py` validates component arrays, components, assertions and assertion types before use, even without bindings. Authentic pinned export mutations use matching bindings; positive model-judgment fixture and source preservation retained. |
| P03 | Defective behavioral reuse | Equal and changed bundle cases reject mutable aliases and unknown mapping values with unknown/exit 4. Static/immutable controls, stale/unapproved evidence, governed changes, routing and conflicting approved records retain explicit gate states and reruns. |
| P04 | Implemented; remote workflow acceptance unverified | CLI manifest/import/compare/history tests and immutable temporary-Git policy/checker tampering. Workflow adds explicit trusted policy and candidate evidence paths for authored static controls; live evaluation remains externally unavailable. |

## Reproductions and local verification

The untouched baseline suite on CPython 3.12.13 with constrained dev/tiktoken dependencies passed: 1,164 passed, four Python-3.10-only skips. Its measured coverage was 92.59% with the baseline loaded through `PYTHONPATH`; this is a separate source-layout measurement, not the corrected checkout's coverage. The unconditional `tomli` development declaration was already fixed at baseline.

The reported A–D defects were reproduced with new tests before implementation. Three initial test expectations were corrected after inspecting existing contracts: reference definitions retain their definition line, and an existing empty history store is a valid zero-run ledger. The corrected tests preserve those behaviors. The original offline test failed when inherited lowercase `no_proxy=*` allowed a real cold download; the fixed test uses a held non-listening local socket and isolated caches. A separate regression reproduced a list-valued trusted check kind escaping as `TypeError` before its type validation was added.

Fresh constrained environments:

- `/tmp/tracemantle-audit-310`: CPython 3.10.14, `pip install -c constraints-dev.txt -e '.[dev]'`, no tiktoken.
- `/tmp/tracemantle-audit-312`: CPython 3.12.13, `pip install -c constraints-dev.txt -e '.[dev,tiktoken]'`; constrained `strictyaml` and `click` added for the pinned reference checker.
- `/tmp/tracemantle-audit-312-minimal`: fresh CPython 3.12.13, constrained dev extras only, no tiktoken. Strict mypy verifies that the already-fixed dev `tomli` declaration suffices on this host.

Final local acceptance passed:

| Command/environment | Result |
|---|---|
| `python -m pytest -q --cov-fail-under=80`, clean 3.10 dev, no tiktoken | 1,266 passed; 87.89% coverage; [log](tests-python310.txt) |
| Same command, clean 3.12 dev/tiktoken | 1,262 passed, four expected version-specific skips; 87.79%; [log](tests-python312-tokenizer.txt) |
| `make verify-release`, clean 3.12 dev, no tiktoken | 1,262 passed, four expected skips; 87.82%; lint, strict typing, self-host, wheel/source build and clean installs passed; [retained tail](tests-python312-minimal.txt) |
| `ruff check src tests scripts`, `mypy`, generated-reference `--check`, `git diff --check` | Passed; strict mypy covers 73 source files and also passed in the fresh 3.12 dev-only environment |
| `verify_reference_corpus.py`, `calibrate_advisories.py` | 10 agreements, three documented divergences; 37.394% median token error, 11 TP/12 TN/0 FP/1 FN, eight semantic abstentions |
| `verify_artifacts.py candidate-dist --legacy-wheel … --output …` on 3.10 and 3.12 | Clean wheel/source installs and old-uninstall/new-install migration passed; [3.10 hashes](artifacts-python310.json), [3.12 hashes](artifacts-python312.json) |
| Real CLI manifest, bound authentic import, history write/read, repeated explicit migration | Passed with expected 0/4 exit codes, four model-judgment records, byte-preserved sources and idempotent migration; [CLI reports](cli.json) |
| Lowercase bypass environment, fixed cold-offline test | Passed with `no_proxy=*`, empty lowercase HTTP/HTTPS/all-proxy settings inherited; explicit tiktoken fails and heuristic succeeds |

Dependency versions are in [dependencies.json](dependencies.json), code and unchanged plan hashes in [source.json](source.json), and command metadata in [local.json](local.json). The full local release log is `/tmp/tracemantle-audit-verify-release.log`. Two subsequent candidate-policy/checker and workflow-boundary assertions passed in targeted real-process tests; all runtime source is the same as the full-suite runs. Remote run identities will be appended after execution. Intermediate failing runs are not substituted for final acceptance. The 80% coverage gate, strict typing and meaningful assertions are unchanged.

## Performance

The fresh baseline and corrected-source benchmark use `scripts/benchmark.py --repeats 5`, CPython 3.12.13, macOS 26.6.2 arm64, explicit word/punctuation heuristic, warm filesystem cache and fresh processes for cold CLI timing. Corpus shape, implementation hashes, all repetitions, median/spread and peak Python allocations are retained in [baseline-performance.json](baseline-performance.json) and [current-performance.json](current-performance.json). The benchmark includes 1/100/1,000 skills, graph/report reuse, 500 references, near-limit imports and 1,000-entry legacy/immutable history. Every current planned workload median stayed within the 10% regression budget. The supplemental 1,000-case code-context workload removed 2,000 false dependencies and improved median tokenization time by 8.9%. [Timing table and reproducible commands](performance.md). The historical comparison against 1.5.0 remains in [performance.md](../performance.md), including its correctness exceptions.

## Remote acceptance and external boundary

Before integration, `main` had no branch protection or rulesets, and the configured Git author was `moonrunnerkc`. Existing final-baseline CI run 34727841804 passed but does not establish checks on these fixes. Publishing remained `disabled_manually` with `TRACEMANTLE_PUBLISH_ENABLED=false`. Only ordinary main CI and explicitly selected nonpublishing comparison/guard runs are authorized here.

No authorized live agent/skill runtime and evaluation budget were supplied. Actual observed invocation, routing quality and behavioral task-success measurements therefore remain unexecuted under P02–P04/D11. All new evidence controls are labeled synthetic; the retained Promptfoo export demonstrates upstream format compatibility and model judgments only. Vendor runtime applicability and semantic advisory calibration remain explicitly unverified as documented. This audit does not declare those empirical criteria complete.

## Executed remote workflow controls

Implementation commit `b9bc5ff3b121fe6ca0d5ed72595c16d6ee68e13e` reached `main` by normal push after all available local gates passed. The original static fixture at that revision is the immutable trusted control for subsequent candidate tampering. [Remote run identities](remote.json) retain exact workflow SHAs and individual job conclusions.

- [Trusted static control](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732213429): passed, installing only the selected trusted checkout.
- [Missing-evidence control](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732248364): deliberately blocked with unknown, exit 4; GitHub marked the comparison job failed as expected.
- [Nonpublishing release guard](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732214620): deliberate quality failure, publishing sentinel skipped, verification job passed. The overall workflow conclusion is failure by design. It contains no publishing capability. The real Release workflow and enable variable stayed disabled.

Candidate commit `f0187a2cf5f71eed39d1cfdd09f94cc040a60ed8` changes the governed helper, marks its own policy check optional and substitutes a checker that raises if executed. Local CLI comparison against the immutable control reports only `helper.py` changed, retains the required static check and requires a rerun (unknown, exit 4); the candidate checker does not execute. The fixture README documents the two revisions and replay command. [Remote candidate comparison](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732389457) confirmed unknown/exit 4 with the governed helper changed and the check still required. No candidate checker ran. Both [implementation CI](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732204839) and [candidate-fixture CI](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732370867) passed all 15 jobs on their respective exact commits. Their wheel/source verification reports and hashes are retained in `remote.json`.

Final review added five Markdown controls: two preserve explicit filenames with parentheses/brackets and three distinguish code examples containing resource-like links/references/directives. Two failing regressions exposed the overly narrow path filter before its correction. The subsequent full suites passed: 1,271 tests on Python 3.10 at 87.90%; 1,267 passed and four expected skips on Python 3.12 with tiktoken at 87.79%. See `tests-python310-final.txt`, `tests-python312-tokenizer-final.txt` and `source-final.json`. These later changes require another exact-commit remote CI run; the final SHA and completed CI link are reported at handoff. Earlier runs remain revision-specific evidence.

The final fresh 3.12 dev-only `make verify-release` also passed: 1,267 passed, four expected skips, 87.82% coverage, Ruff, strict mypy, self-host symbolic/graph checks, wheel/source build and clean installs. Final command log: `/tmp/tracemantle-audit-verify-release-final.log`; retained tail: `tests-python312-minimal-final.txt`. The final code-context benchmark remains within budget (15.485 ms median, 5.2% below the unchanged baseline); all representative workload medians meet the 10% limit. Final source artifact migrations on both interpreters are recorded separately in `artifacts-final-python310.json` and `artifacts-final-python312.json`. The intermediate logs and hashes above remain historical to their source snapshots.

## Adjacent YAML scalar conversion correction

Commit `d010692c45816e0b8646a62cea06f23b5ef03409` [passed all 15 CI jobs](https://github.com/moonrunnerkc/tracemantle/actions/runs/34732747534), with repeated trusted control, candidate tampering and nonpublishing guard outcomes retained in `remote.json`. A subsequent adjacent-input probe found that PyYAML raises plain `ValueError` for invalid date/time values and oversized integer conversion. Four failing real-process regressions reproduced the uncaught errors before correction.

`parser.py::_Loader.construct_object` now normalizes conversion errors only for YAML integer, float and timestamp tags, with a bounded message and the scalar's full-file line. Other tags' `ValueError` exceptions still propagate so programming defects are not hidden. Valid dates retain their YAML type and manifest string validation; no arbitrary value is coerced to a description. Regression cases cover invalid month, hour, timezone and a 5,000-digit integer with an explicit interpreter digit limit. Validation JSON continues the valid companion file and exits 1; manifest JSON reports infrastructure-error and exits 2. This supplements D02/D03/D07 and P01.

The source bytes for this correction are in `source-scalars.json`. Earlier source snapshots and successful runs remain revision-specific evidence. The final scalar-corrected main commit must pass its own complete CI before handoff.

Scalar-corrected local acceptance passed in the same clean constrained environments: **1,275 passed, 87.82%** on 3.10; **1,271 passed, four expected skips, 87.72%** on 3.12 with tiktoken; `make verify-release` without tiktoken passed with **1,271 passed, four skips, 87.74%**. Ruff, strict mypy, generated-reference freshness and diff checks passed. Conformance/calibration were reexecuted and byte-identical to the retained reports. Rebuilt wheel/source migrations passed on both interpreters. See `local-scalars.json`, `tests-python*-scalars.txt` and `artifacts-scalars-python*.json` for this latest source snapshot.

An initial history timing outlier overlapped artifact installation. Repeating both implementations serially after verification finished put every median within the 10% budget; the largest increase was 3.6%. Both noisy and repeated samples remain in the performance record. The final code keeps the one-parse architecture, and no historical 49.8% improvement is claimed as newly reproduced.
