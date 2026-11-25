# Correctness and trust upgrade: acceptance ledger

Work ledger for requirements A through I of the 2026-11-23 review. Evidence
files are in this directory. Local results are from one macOS arm64 machine;
remote results are recorded separately and only for the exact commit named.

## Baseline

| Item | Value |
|---|---|
| Starting commit | `5026e8e83f66c6addcdf45fb68f559f3e05b6a0e` (1.8.0), branch `main`, in sync with `origin/main` |
| Working tree | One uncommitted change, `AGENTS.md`, identical to the local untracked `CLAUDE.md`; carried into this branch |
| Tools | Python 3.10.14, ruff 0.16.4, mypy 2.3.1, pytest 9.1.1, Git 2.54.0 ([baseline-environment.txt](baseline-environment.txt)) |
| Baseline gates | ruff, mypy and reference check passed; 1667 passed, 3 skipped, 95% coverage |
| Review document | `tracemantle-review-2026-11-23.md` was not present; the task text was used |

The review recorded 1,663 passed and 7 skipped. This checkout collected 1,670
tests; the difference in skips is environmental and neither figure is a target.

## Requirements

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| A | Link discovery cannot permit stale approved evidence | Implemented, verified locally | [a-before-5026e8e.txt](a-before-5026e8e.txt), [a-after.txt](a-after.txt), `tests/test_link_dependencies.py` |
| B | Ignore directives only in YAML comments; `--no-inline-ignores` | Implemented, verified locally | [b-before-5026e8e.txt](b-before-5026e8e.txt), [b-after.txt](b-after.txt), `tests/test_inline_ignores.py` |
| C | Incremental selection follows effective configuration | Implemented, verified locally | [c-e-before-5026e8e.txt](c-e-before-5026e8e.txt), [c-e-after.txt](c-e-after.txt), `tests/test_changed_since.py` |
| D | Structured JSON for expected CLI failures | Implemented, verified locally | [d-before-5026e8e.txt](d-before-5026e8e.txt), [d-after.txt](d-after.txt), `tests/test_json_error_contract.py` |
| E | Amortized root discovery, bounded Git output | Implemented, measured | [benchmark-baseline-5026e8e.json](benchmark-baseline-5026e8e.json), [benchmark-candidate.json](benchmark-candidate.json) |
| F | Python 3.14/3.15, dependency maintenance, audit | Implemented, verified locally and in remote CI | [f-local-audit.txt](f-local-audit.txt), `tests/test_dependency_audit.py` |
| G | Evidence-based compatibility claims | Strict-mode correction implemented; runtime claims remain unverified | [g-before-5026e8e.txt](g-before-5026e8e.txt), [g-after.txt](g-after.txt), `docs/profiles.md` |
| H | Repository safeguards | Applied and read back; tag rule not exercised | [h-repository-state-before.txt](h-repository-state-before.txt), [h-repository-state-after.txt](h-repository-state-after.txt) |
| I | Documentation, verification, completion | Done; open items listed under "Not verified" | this file |

Each "before" file is the new regression module run against the unmodified
1.8.0 implementation. Tests listed as failing there fail for the defect; tests
that pass there are the controls.

### A. Link discovery

Reproduced on 1.8.0 with a real temporary trusted Git policy and synthetic
approved evidence, both binding only `SKILL.md`. After changing only
`helper.py`, `compare` exited 0 for these forms and now exits 4 with
`required_reruns: ["validate"]`:

| Form | 1.8.0 | Now |
|---|---|---|
| `Run [helper](helper.py).` (control) | exit 4 | exit 4 |
| `[helper](`, `helper.py`, `)` on three lines | exit 0 | exit 4 |
| `[run [helper]](helper.py)` | exit 0 | exit 4 |
| `[run][helper]` with `[helper]: helper.py` then `[helper]: unused.py` (both files exist) | exit 0, only `unused.py` governed | exit 4, `helper.py` governed |
| Same with the definitions reversed | exit 4 | exit 4, both governed |

Unchanged bundles and unrelated edits still pass for every fully supported
form. Examples inside fenced and indented code are still excluded. Expectations
were derived from CommonMark 0.31.2 sections 4.7 and 6.3.

Design decisions and their cost:

- The scanner is a single forward pass per paragraph block in
  `markdown.py`, with no new dependency. It records every bracket pair that
  matches a defined label, which is a superset of the links CommonMark
  renders. Effect: a document can gain a governed helper that a renderer
  would not link. That direction is safe for evidence reuse.
- CommonMark applies the first definition of a label. A first version of
  this fix kept only the first, and the independent review showed that a
  look-alike the tokenizer cannot rule out (inside an HTML comment, or a
  label differing by a non-breaking space) then hid the real one. Every
  distinct destination for a label is now governed, up to eight. Effect:
  changing a file named only by a later duplicate definition also requires
  a rerun, and a duplicate that names a missing file is a broken link.
- `[text](two words)` and similar destinations that do not parse now mark
  coverage incomplete. Effect: such a document gets exit 4 from `compare`
  until the link is fixed. Prose such as `array[i](x, y)` outside code
  triggers this too.
- Tokenizing a 2.9 MB realistic body took 0.97 s against 0.79 s before on
  this machine. Seventeen adversarial inputs each finish inside the existing
  5 second bound; the slowest measured locally is 0.6 s.

### B. Ignore directives

The `hello` reproduction (directive-shaped line inside `description: |-`,
body `[missing](missing.py)`, `--strict`): exit 0 on 1.8.0 with
`references.broken-link` suppressed; now exit 1 with the error reported and no
`ignore.inline` note. Eight string forms are covered, including chomping and
indentation indicators and both quote styles. Six real-comment controls,
including one directly after a block scalar, still suppress and exit 0.

`--no-inline-ignores` keeps the error (exit 1), reports
`ignore.inline-refused` and still reports invalid tokens. A project
`no-inline-ignores = false` does not override the flag.

### C. Incremental selection

Reproduction: committed skills with a three-line body and
`max-lines = 500`; change only the setting to `max-lines = 1`. Full strict
scan exits 1. `--changed-since HEAD` selected 0 skills and exited 0 on 1.8.0;
it now selects all three, exits 1 and returns the same results as the full
scan. Covered: unstaged, staged and committed edits against the resolved
revision; untracked, deleted and renamed configuration; a nearer
configuration added; legacy `skillcheck.toml`; a `pyproject.toml` gaining or
losing its tool table; explicit `--config` changed, external and ignored;
nested repositories, a linked worktree and a submodule.

Limit, documented in `docs/ci.md`: the selection reflects file changes only.
It does not show that unselected skills pass under a different tool version,
environment or flags.

### D. Structured failures

Sixteen expected failures were checked with `--format json` and
`--format=json`: exit 2, one schema-2 object on stdout, no traceback. The same
sixteen keep stderr text in text mode and under `--quiet`. Argparse-level
errors stay usage errors on stderr. Evidence commands keep schema 1. An
unexpected `KeyError` still propagates.

One existing assertion changed with the contract:
`tests/test_profile_freshness.py` expected stderr text while passing
`--format json`; it now expects the envelope and separately checks text mode.

Behavior change to note: `--quiet --format json` configuration errors printed
JSON before and now print stderr text, like every other failure under `--quiet`.

### E. Performance

Workload: one seeded repository of 500 skills with a helper each, plus a
50-skill nested repository for the last scenario; `--strict --format json`;
7 repetitions; medians; Python 3.10.14, Git 2.54.0, macOS arm64. Git ran
through a counting shell shim, which adds a shell start to every Git call and
so overstates the baseline's incremental time.

| Scenario | Scan | 1.8.0 median | Candidate median | Git processes | Selected (1.8.0 / candidate) |
|---|---|---|---|---|---|
| No changes | full | 0.269 s | 0.277 s | 0 / 0 | 500 / 500 |
| No changes | incremental | 6.787 s | 0.255 s | 503 / 5 | 0 / 0 |
| One changed skill | incremental | 7.290 s | 0.256 s | 503 / 5 | 1 / 1 |
| Shared configuration change | incremental | 6.205 s | 0.417 s | 503 / 4 | 0 (exit 0) / 500 (exit 1) |
| Nested repository, one change | incremental | 6.798 s | 0.294 s | 556 / 9 | 1 / 1 |

Selected paths and per-file verdicts are identical between baseline and
candidate in every scenario except the shared configuration change, which is
the defect fixed in C. The candidate's incremental run with no changes is only
slightly faster than a full scan of 500 small skills on this machine (0.255 s
against 0.277 s): interpreter start and configuration discovery dominate. The
benefit is removing the per-skill Git cost, not beating a full scan at this
size.
No timing assertion was added to the test suite. Selective evidence reuse
remains optional and experimental; no new study was run.

### F. Python support and dependencies

Upstream status read on 2026-11-23 from
<https://devguide.python.org/versions/>: 3.10 end of life (2026-10-01); 3.11,
3.12 and 3.13 security; 3.14 and 3.15 bugfix (3.15.0 released 2026-10-09).
`actions/python-versions` lists stable 3.14.10 and 3.15.2 for Linux, macOS and
Windows.

- PyYAML 6.0.3 and regex 2026.7.19 publish no CPython 3.15 wheels. PyYAML
  moves to 6.0.4. regex 2026.11.19 requires Python 3.11, so the constraint is
  split by interpreter marker.
- The audit reported PYSEC-2026-4320 against certifi 2026.7.22 and
  PYSEC-2026-4175, 4176 and 4177 against urllib3 2.7.0, all reached through
  the `tiktoken` extra. Both pins moved to the fixed releases; the rerun is
  clean on 3.10 and 3.15 ([f-local-audit.txt](f-local-audit.txt)). No advisory
  is ignored.
- pip-audit 2.10.1 behavior was observed directly: exit 1 with a JSON report
  for advisories, exit 1 with no report when the advisory service is
  unreachable, exit 0 with a `skip_reason` row for an unknown package. The
  wrapper maps these to exit 1, 2 and 2.
- Local installs and full suites: 3.10, 3.14 and 3.15 without the tokenizer;
  3.10 and 3.15 with it. Python 3.15.2 came from a checksum-verified
  python-build-standalone archive kept outside the repository.
- Dependabot: the `pip` ecosystem documents support for any `.txt` file and
  PEP 621 `pyproject.toml`. Its handling of the marker-qualified constraint
  lines has not been observed and is not claimed. `uv.lock` was refreshed with
  `uv lock`; no Dependabot `uv` entry was added, to avoid two ecosystems
  proposing the same `pyproject.toml` change.
- Actions pins were left as they are. Newer majors exist; moving them is left
  to the reviewed Dependabot proposals. The PyPI publish action keeps its
  version tag for the container-reference reason recorded in `release.yml`.

### G. Compatibility claims

Implemented: general `--strict` no longer promotes the VS Code directory
note or the Cursor block-scalar note. The explicit flags, config keys and
Action inputs still do, and their messages name the selected policy.
Twenty-five CLI cases cover the interaction with `--target-agent` and project
configuration.

Verified by reading documentation only (2026-11-23), recorded in
`docs/profiles.md`: what the specification and the four vendor pages state
about name and directory matching, description format and frontmatter fields.

Not verified: any runtime behavior. No skill was loaded in Claude Code
2.1.331, codex-cli 0.162.1 or VS Code 1.138.0, because that starts a model
session, and no Cursor runtime was available. `verified.toml` and
`compatibility-v1.json` are unchanged: `verified_on` stays 2026-04-20,
`confirmed` and `contradicted` stay empty, `runtime_applicability` stays
`unverified`. Next step: load a fixture skill in a pinned runtime version and
record version, fixture, command and outcome before changing any claim.

### Issues 20 and 21

The exact examples were rerun ([issues-20-21.txt](issues-20-21.txt)). Both
already behaved this way at 1.8.0; this work did not change them.

- Issue 20 (runtime data paths): eight `references.uncertain` warnings, no
  `references.escape` error. Exit 0; exit 1 under `--strict`; exit 0 with
  `--strict --ignore references.uncertain`.
- Issue 21 (glob pattern): one `references.uncertain` warning, no
  `references.broken-link` error. Same exit codes.

The direction agreed in the issue threads (an info-level `references.external`
for home and absolute paths, skipping glob spans without affecting coverage)
is not implemented. Proposed replies are in the pull request description.

## Independent review of the pushed branch

The first pushed head (`3cfca0f`) was reviewed by a separate read-only pass
that ran its own inputs, and its first remote CI run failed. Both led to
changes; [review-before-3cfca0f.txt](review-before-3cfca0f.txt) lists the added
regressions failing on that head.

| Finding | Origin | Resolution |
|---|---|---|
| Two crafted inputs took 5 to 9 s under coverage on CI runners (limit 5 s) | This branch | Failed destination scans are limited per block; 1.4 s to 0.17 s locally |
| "First definition wins" let a look-alike hide the real definition | This branch | Every distinct destination per label is governed |
| Slicing bracket text before checking nesting was quadratic (12 s at 2 MB) | This branch | Length is checked before slicing; 0.5 s |
| Multi-line label containing a backslash was silently not a definition | This branch | Labels are scanned with escapes; no regex fallback |
| Git-ignored discovered configuration was treated as unchanged | This branch | Configuration with no baseline selects the skills it applies to |
| `<a` plus spaces, and long `file:` runs, backtracked quadratically | 1.8.0 | Both patterns made linear |
| Backtick inside an HTML tag, comment or autolink, or on a definition line, hid later links | 1.8.0 | Coverage is marked incomplete |
| Vertical tab, form feed and similar characters split lines and opened a fence | 1.8.0 | Coverage is marked incomplete |
| A line holding only a non-breaking space was treated as blank | 1.8.0 | Only spaces and tabs make a line blank |
| `2.` or an empty item split a paragraph | 1.8.0 | Such items no longer interrupt a paragraph |
| Changed paths compared by exact spelling (Unicode form, case) | 1.8.0 | Compared after NFC normalization and case folding |

The second remote run (`21e723a`) failed one new timing case on Python 3.10
to 3.13: 200,000 definitions followed by 200,000 uses took about 7 s under
coverage tracing. Local scaling is linear (25,000, 50,000, 100,000 and
200,000 repeats took 0.16, 0.33, 0.66 and 1.33 s), so the input was resized to
50,000 repeats; the code did not change.

The review found no defect in the YAML comment detection (300,000 generated
documents compared with PyYAML), the bounded Git runner, the JSON error
boundary or the CI gate and audit jobs. It did not run on Windows and did not
exercise worktrees or submodules; the test suite does both for worktrees and
submodules, and remote CI covers Windows.

Known remaining limits of the tokenizer, unchanged by this work: HTML blocks
are not parsed, so a link inside one is still reported; block quotes and lazy
continuations keep coverage incomplete; and code spans are matched before
block-level definitions, which is why a backtick on a definition line now
marks coverage incomplete rather than being resolved exactly.

Correction, 2026-11-24: the statement above that an unparsed HTML block only
adds a reported link was wrong. A fence marker inside an HTML block was read
as a fence, which hid a real link after the block while coverage stayed
complete. The omission existed at 1.8.0 and at this work's merge; it was found
by the 2026-11-24 review and is resolved in 1.9.0. See the
[closeout record](../correctness-trust-closeout/acceptance.md).

## Repository safeguards

State before: `main` unprotected, no rulesets, private vulnerability reporting
off ([h-repository-state-before.txt](h-repository-state-before.txt)). State
after, read back from the API
([h-repository-state-after.txt](h-repository-state-after.txt)):

| Control | Applied | Detail |
|---|---|---|
| Ruleset 27949490, `main` | Yes | Blocks deletion and non-fast-forward pushes; requires a pull request with 0 approvals; requires the `CI gate` check from GitHub Actions (app 15368). No bypass actors. |
| Ruleset 27947876, version tags | Yes | `refs/tags/v*.*.*` cannot be updated or deleted. No bypass actors. Creating a new version tag is still allowed. |
| Private vulnerability reporting | Yes | `enabled: true` after the change. |
| Release workflow, `TRACEMANTLE_PUBLISH_ENABLED`, secrets, tags | Unchanged | Release stays disabled and the variable stays `false`. No tag was created, moved or deleted. |

The `CI gate` identity was taken from the check run on pull request head
`707f79f` (name `CI gate`, app `github-actions`, id 15368) before it was
required. Definitions as submitted: [ruleset-main.json](ruleset-main.json),
[ruleset-version-tags.json](ruleset-version-tags.json). GitHub added its
default `require_extra_approval_for_unattributed_changes: true` to the pull
request rule; it was not requested and was left as returned.

What was and was not exercised:

- The gate job was observed failing on the first two heads: one failed test
  job left `package` and `artifacts` skipped and `CI gate` failed, not passed.
- The branch rule was exercised by this pull request, which had to pass
  `CI gate` on its final head before it could merge.
- The tag rule was read back but not exercised. Testing it means trying to
  move or delete a tag in the release namespace, and a probe tag created for
  the purpose could not be removed afterwards.
- The moving `v1` tag is outside the pattern (`File.fnmatch` with
  `FNM_PATHNAME` returns false for `refs/tags/v1`), so the `move-major-tag`
  job needs no bypass. No claim is made that any rule is limited to a
  particular workflow.

Operational consequences for the maintainer:

- Direct pushes to `main` are now rejected. Every change needs a pull request
  whose head passed `CI gate`.
- `release-notes.yml` opens its changelog pull request with the workflow
  token, and GitHub does not start workflows for pull requests created that
  way. `CI gate` will not report on it until a maintainer closes and reopens
  the pull request or pushes a commit to its branch.
- A published version tag can no longer be corrected in place. A bad tag needs
  a new version.

Rollback: `gh api -X DELETE repos/moonrunnerkc/tracemantle/rulesets/27949490`
removes the branch rule and `.../rulesets/27947876` the tag rule; setting
`"enforcement": "disabled"` with `PUT` keeps the definition.
`gh api -X DELETE repos/moonrunnerkc/tracemantle/private-vulnerability-reporting`
turns reporting off. Each returns the repository to the "before" state for
that control.

## Verification

Local, macOS arm64, final code (`21e723a`; `707f79f` changes one test input):

| Environment | Result |
|---|---|
| Python 3.10.14, no tokenizer | `make verify-release` passed: ruff, mypy, 1923 passed, 3 skipped, 96% coverage, build, clean wheel and source installs. Reference check passed. |
| Python 3.10.14 with tiktoken | 1922 passed, 4 skipped, 95.73% |
| Python 3.14.7, no tokenizer | 1917 passed, 9 skipped, 95.60% |
| Python 3.15.2, no tokenizer | 1917 passed, 9 skipped, 95.60% |
| Python 3.15.2 with tiktoken | 1918 passed, 8 skipped, 95.63% |

Local skips: minisign and bubblewrap are not installed here (two tests), the
offline tokenizer test needs tiktoken, four `tomli` fallback tests run only on
3.10, and two pre-commit tests need the `pre-commit` binary on `PATH`. OpenSSH
signature tests ran locally.

Remote CI on `707f79fcfb28352cf1b20247fb8890d3e4d603b4`, run 45296882634: all
29 jobs succeeded. That covers 18 test jobs (Linux, macOS and Windows on
Python 3.10 to 3.15), `lint`, `tokenizer` on 3.10, 3.12 and 3.15, `approvals`
(real OpenSSH and minisign signatures and the bubblewrap producer test, with
skips rejected, plus the Action from this source), `package`, `artifacts` on
3.10 and 3.15, `audit` on 3.10 and 3.15, and `CI gate`.

This ledger was committed after that run, so the commit that contains it has
its own later run. The pull request records the run for the merged head.

## Not verified, and intended debt

| Item | Practical effect | Next action |
|---|---|---|
| No agent runtime loaded a skill | Compatibility notes remain historical advice | Record a pinned-runtime observation, then update `verified.toml` |
| Tag ruleset not exercised | Its effect rests on the API read-back | None planned; see above |
| Dependabot not yet observed | It may not update marker-qualified constraint lines | Check its first pull requests |
| Issues 20 and 21 keep `references.uncertain` | Strict runs still fail on documented paths and globs unless ignored | Implement the direction agreed in the issues |
| HTML blocks are not parsed | A link inside an HTML block is still treated as a dependency. Corrected 2026-11-24: a fence marker inside one could also hide a later real link | Resolved in 1.9.0; see the [closeout record](../correctness-trust-closeout/acceptance.md) |
| Every definition of a duplicated label is governed | A duplicate naming a missing file is a broken link | Accept; documented in contracts |
| `strict_all` is still accepted by `get_rules` and `validate` | An unused parameter kept for API compatibility | Remove in a major version |
| Actions pins not moved to current majors | Older pinned majors keep running | Review the Dependabot proposals |
| Python 3.10 retained past end of life | One legacy lane and the `tomli` fallback remain | Remove by the process in `docs/migration.md` |
