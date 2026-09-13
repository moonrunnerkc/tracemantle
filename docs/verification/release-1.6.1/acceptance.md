# TraceMantle 1.6.1 verification

The owner authorized code changes, normal pushes, a new patch tag, GitHub release and production PyPI publication. Starting source and fetched `origin/main` were `79f8fdf5dfe4f4004eb5926359c7b13c44fc8519`, with a clean tracked working tree. Case-insensitive instruction discovery found no ancestor or source/test/docs instructions; `.github/CLAUDE.md` was read and remains unchanged. The complete original DOCX, including both tables, was read and its bytes are preserved. GitHub and PyPI reported 1.6.0 as latest, with 1.6.1 unused. The repository rename and trusted publisher were inspected, not reprovisioned.

## Correction and acceptance

D09/P01/P03: Setext underlines terminate the preceding paragraph as a heading before inline spans are matched. This preserves spans inside multiline heading content while preventing a following paragraph from closing an unmatched heading delimiter. Indented ATX headings and spaced homogeneous thematic breaks had the adjacent boundary mechanism and now delimit spans too. Four-column paragraph continuation and invalid underlines retain paragraph semantics. Code blocks are handled first; supported list indentation remains container-relative. Unsupported containers still mark coverage incomplete.

`tests/test_setext_dependencies.py` reuses the real CLI and temporary trusted-Git acceptance infrastructure. Both check and approved synthetic evidence explicitly declare only `SKILL.md`. A helper-only candidate change must produce unknown, exit 4, and required rerun `validate`; unchanged and unrelated-change controls pass when coverage is complete. Code examples do not govern the helper. The existing 75 dependency/numeric cases remain intact, as do required-unknown and candidate-policy/checker controls.

The initial 53 new cases, run before any implementation change, produced **17 failures and 36 passes** on the audited source. [Original log](tests-original-setext.txt) records both minimal heading failures. The final targeted selection passed **318 tests**, including all 57 heading/boundary cases, the existing 75 dependency/numeric regressions, audit cases, trusted product acceptance and references. [Targeted log](tests-targeted.txt). The unsupported outdented case still blocks approval, but its expected best-effort dependency list now includes the exposed helper.

## Verification status

Full suites, performance, clean artifacts and exact-commit remote checks are recorded below as they complete. Earlier records under `audit-1.6.1/` are historical source snapshots, not evidence for this release. No quality threshold, assertion, runtime dependency or instruction file was weakened. No live skill/evaluator execution or paid evaluation was initiated. Static compatibility and upstream export parsing do not establish live agent behavior.

## Local quality gates

Constrained environments were reinstalled with `pip install -c constraints-dev.txt -e '.[dev]'`, adding `[tiktoken]` only in the tokenizer environment. Full commands preserve `--cov-fail-under=80` and separate coverage output files.

| Environment and command | Result |
|---|---|
| CPython 3.10.14, no tiktoken, `python -m pytest -q --cov-fail-under=80` | 1,407 passed; 89.32% coverage; [log](tests-python310.txt) |
| CPython 3.12.13, tiktoken 0.14.0, same full-suite command | 1,403 passed, four expected 3.10-only skips; 89.22%; [log](tests-python312-tokenizer.txt) |
| CPython 3.12.13, no tiktoken, `make verify-release` | 1,403 passed, four expected skips; 89.25%; [retained tail](tests-python312-minimal.txt) |
| Ruff, strict mypy, generated reference freshness, changelog release gate, diff whitespace | Passed; strict typing checks 73 source files |
| Self-host symbolic and graph validation, clean wheel/source builds and installed checks | Passed in the full release gate |
| Reference conformance and held-out calibration | 10 agreements, three documented divergences; unchanged 37.394% median token error; [conformance](conformance.json), [calibration](calibration.json) |

The four Python 3.12 skips exercise the Python 3.10 TOML fallback and run on 3.10. Pre-commit integration and offline tokenizer isolation ran. Mutable model aliases, unknown execution context, malformed nested Promptfoo structures, configuration/YAML errors, history escaping and candidate-controlled policy/checker regressions passed. The package verifier now checks both reported headings and the JSON infrastructure-error/exit-2 overflow envelope from isolated installed artifacts, and CI invokes the same verifier before publishing.

## Performance and source identity

[Serial performance checks](performance.md) retain all repetitions and justified correctness costs. Representative graph/report and preserved parser workloads meet the 10% median budget; the newly discovered heading links and adversarial spaced-marker scans have bounded, documented costs. [Source hashes](source.json) include runtime files, tests, packaging constraints and the unchanged original plan. [Installed development dependencies](dependencies.json) identify all three local configurations.

The final 57-case heading suite was replayed against the detached audited source with explicit source selection. It produced **19 failures and 38 passes**, including the heading-to-indented-code control. It remains a negative control; [full original-source replay](tests-final-against-original.txt) records its failures. No failing run is presented as release approval.

Retained pytest logs normalize trailing whitespace only; command outcomes and assertions are unchanged. Clean indexed-tree wheel/source verification uses `scripts/verify_artifacts.py --legacy-wheel` on both Python 3.10 and 3.12. The artifact JSON files are excluded from source archives by the existing packaging rule to avoid recursive digests.
