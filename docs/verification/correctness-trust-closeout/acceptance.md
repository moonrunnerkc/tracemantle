# Correctness and trust closeout

Two false passes found by the 2026-11-24 review of the
[correctness and trust upgrade](../correctness-trust-upgrade/acceptance.md).
Both existed at 1.8.0 and at that upgrade's merge; neither was a regression.
This record covers the implementation. The release that delivers it is
recorded separately in [release.md](release.md) once published.

No skill content, helper or model was executed. The approved evidence in the
comparison tests is a synthetic policy control. Runtime compatibility profiles
remain unverified.

| | |
|---|---|
| Starting commit | `bae6ef47a725df9c6cdbdf85bc6d857711118d69` (`main`, package version 1.8.0) |
| Branch | `fix/html-block-and-symlinked-config` |
| Local environment | macOS 26.7.3 arm64, CPython 3.10.14, Git 2.54.0 |
| Oracle environment | CPython 3.12, markdown-it-py 4.0.0 in CommonMark mode, outside the project environment |

## 1. HTML block contents concealed a later helper dependency

**Requirement.** A real link after an HTML block must be governed, or
dependency coverage must be incomplete. An omitted dependency must never be
combined with complete coverage.

**Defect.** The tokenizer did not recognize HTML blocks, so a fence marker
inside one opened a code block that swallowed the rest of the document.
[CommonMark 0.31.2 section 4.6](https://spec.commonmark.org/0.31.2/#html-blocks)
treats those lines as raw HTML ([example 161](https://spec.commonmark.org/0.31.2/#example-161)).

**Before**, at `bae6ef4`, for each of the three reviewed bodies, with policy
and evidence binding only `SKILL.md` and only `helper.py` edited
([reproduce-before-bae6ef4.jsonl](reproduce-before-bae6ef4.jsonl)):

| Body | `manifest.complete` | Helper edge | `compare` exit | State | `changed_inputs` | `required_reruns` |
|---|---|---|---|---|---|---|
| comment with `~~~` | true | absent | 0 | pass | `helper.py` | none |
| `<div>` with a backtick fence | true | absent | 0 | pass | `helper.py` | none |
| `<pre>` with `~~~` | true | absent | 0 | pass | `helper.py` | none |

**After** ([reproduce-after.jsonl](reproduce-after.jsonl)): all three report
`complete` true with the edge `SKILL.md -> helper.py`, and the comparison
exits 4 with state `unknown`, `changed_inputs` `helper.py` and
`required_reruns` `validate`.

**Resolution.** `_blocks` in `src/tracemantle/markdown.py` recognizes the seven
HTML block start conditions and their end conditions, including that only a
lone tag cannot interrupt a paragraph and that a block ends with its list
item. Lines of a block are kept as raw HTML content: fence markers and
backticks there are literal, while `href`, `src` and link syntax inside the
block stay governed, as before. No renderer or dependency was added and HTML
is never executed.

Deliberate conservative results, each asserted in
`tests/test_link_dependencies.py`. A bundle with one of these forms compares
as unknown even when unchanged:

- A line that starts with a `<textarea>`, `<search>` or `<source>` tag, or a
  lowercase declaration such as `<!doctype`. CommonMark 0.31.2 and the 0.29
  revision that GitHub Flavored Markdown follows disagree about them.
- A blank line inside a comment or `<pre>`-style block within a list item.
  The specification continues the block; markdown-it-py ends it.
- A Setext underline after a paragraph that begins with a link reference
  definition. If definitions consume the paragraph the line is text.

**Regression evidence.**

- [html-blocks-before.txt](html-blocks-before.txt): the new tests run against
  the unmodified tokenizer. They fail on the missing helper edge, not on
  setup.
- `test_link_forms_control_real_trusted_comparison` gains the three reviewed
  bodies. It uses a real temporary bundle, a real temporary Git trust
  repository, the real CLI and a policy and record that bind only `SKILL.md`.
  Its existing rows still show that an ordinary link invalidates on a helper
  change, that a link inside a fenced example stays excluded, and that an
  unchanged bundle and an unrelated edit keep exit 0.
- Further tokenizer cases cover every HTML block kind with both fence
  characters, mixed case, blank lines inside a block, list items, links that
  stay excluded inside genuine fences next to HTML, and dependencies named
  inside a block. Each expectation was checked against markdown-it-py before
  the fix was written.
- [differential-html-blocks.jsonl](differential-html-blocks.jsonl): random
  documents built from HTML, fence, list and link lines, compared with
  markdown-it-py by [differential_html_blocks.py](differential_html_blocks.py).
  At `bae6ef4`, 140 of 300,000 documents had a rendered `helper.py` link that
  was neither reported nor marked incomplete. With the fix, 0 of 900,000.
  Earlier runs with smaller vocabularies, used while iterating, are not
  retained. This is a search over a chosen vocabulary, not a proof.
- Two adversarial inputs were added to the existing linear-time cases. A
  400,000 byte tag with 200,000 attributes took 0.03 s and 1.2 MB of
  `<div>` lines took 0.29 s; both doubled when the input doubled.

Schema-3 closed check scopes and their restrictions are unchanged; no file
under that contract was edited.

## 2. Discovered configuration behind a symbolic link

**Requirement.** `--changed-since` must not return an empty successful
selection when the effective configuration changed through a symbolic link.

**Defect.** Configuration loading follows a link, but change selection
compared only the link's own Git entry. An unchanged link was accepted as an
unchanged configuration.

**Before and after**, in the reviewed repository (`hello/SKILL.md`, a
committed root `tracemantle.toml` linking to `config/policy.toml`, and only
the target changed from `max-lines = 500` to `max-lines = 1`). Each cell is
files checked and exit status:

| Command | Target state | `bae6ef4` | Fixed |
|---|---|---|---|
| `tracemantle hello --strict --format json` | unstaged | 1, exit 1 | 1, exit 1 |
| same with `--changed-since HEAD` | unstaged | 0, exit 0 | 1, exit 1 |
| same with `--changed-since HEAD --config tracemantle.toml` | unstaged | 1, exit 1 | 1, exit 1 |
| same with `--changed-since HEAD` | staged | 0, exit 0 | 1, exit 1 |
| same with `--changed-since HEAD~1` | committed | 0, exit 0 | 1, exit 1 |
| same with `--changed-since HEAD` | committed | 0, exit 0 | 0, exit 0 |

The last row is correct in both: nothing changed since that commit.

**Resolution.** In `src/tracemantle/git_changes.py`, a linked configuration
file counts as unchanged only when all of these hold: the link and its target
are committed in the same repository, the link resolves to the target in one
step through no other link, and Git reports neither as changed. Anything else
selects the skills that configuration applies to and says so on stderr:

| Case | Policy |
|---|---|
| Target edited, staged or committed | Selected |
| Link retargeted | Selected (the link itself changed) |
| Chain of links, or a linked directory in the target path, changed or not | Selected |
| Link text that normalization would alter, such as `name/../file` | Selected: it resolves only while `name` exists, which Git does not record |
| Target outside the repository | Selected |
| Target git-ignored or untracked | Selected |
| Broken link, including a deleted target | Selected |
| Cyclic link | Selected |
| `--config` given through a linked file or a linked directory | Compared by the same rule for a linked file. A linked directory kept in the repository, or resolving inside it, selects every skill |

Discovery itself is unchanged: a broken or cyclic configuration link is still
ignored when configuration is loaded, exactly as before, so a full scan and
an incremental scan of that state agree. Nearest-root precedence, explicit
`--config`, ignored, new and deleted configuration, nested repositories,
worktrees and submodules keep their existing tests. The count of Git
processes for one repository with regular configuration is unchanged, as
`test_one_repository_is_discovered_once` still asserts.

The review also asked that a retargeted link not be mistaken for an unchanged
path. That reproduced for `--config`: a link or a linked directory retargeted
to another unchanged committed file selected nothing at `bae6ef4`. It is
fixed by the same rule and covered by
`test_explicit_symlinked_configuration_is_compared_through_its_link`.

**Regression evidence.** [symlinked-config-before.txt](symlinked-config-before.txt)
lists the new tests failing against the unmodified module; the unchanged-link
and selectivity cases pass before and after. The tests build real Git
repositories and real links. They skip on Windows, where creating a link
needs privileges, and run on Linux and macOS.

## Review of the diff

A separate agent session reviewed the uncommitted diff without the
implementation narrative, with the CommonMark oracle and its own fuzzers
(about 2.6 million documents) and temporary Git repositories. It was an
automated review, not a human one. It found five problems in the first
version of this change, all fixed before the first commit and each covered by
a test that failed first:

| Finding | Resolution |
|---|---|
| `<?>`, `<!-->` and `<!--->` never ended their block, because the end text was searched only after the opener | The whole start line is searched, as the specification says |
| A lone tag after `[d]: x` and `===` was read as an HTML block, although that paragraph stays open | Such a Setext line marks coverage incomplete. This also closes the same misreading before indented code, which predates this work |
| `<!x>` starts a block in 0.31.2 but not in 0.29 or markdown-it-py | Lowercase declarations mark coverage incomplete |
| Link text `x/../cfg/base.toml` compared equal while `x` was created or removed, which Git does not show | Link text that normalization would alter is not shown unchanged, and resolution is strict |
| A tracked directory link on a `--config` path, retargeted to the repository root, was skipped | A directory link kept in the repository is never skipped |

Among the forms it found that predate this work, one had a one-line fix and
is included: a lone `-` outdented below a list item's paragraph was read as a
Setext underline, so a link indented four columns under it became code.

It also reported that markdown-it-py ends a comment or `<pre>`-style block at
a blank line inside a list item, where the specification continues it. That
form now marks coverage incomplete.

The review found link forms that are missed at 1.8.0 as well and are outside
these two requirements. They are listed under retained limits and were
reported to the owner with reproductions.

## Retained limits

This table describes 1.9.0. Most of it was resolved afterwards; see the
[follow-up record](followup.md).

| Limit | Practical effect | Next step |
|---|---|---|
| A multi-hop or external configuration link is never shown unchanged | Every incremental run validates the skills it applies to | Commit a regular file or link directly to a committed one |
| A directory link on a `--config` path that is kept outside the repository and resolves to its root or above is treated as the spelling of the repository's location | Retargeting such a link to a different repository is outside this repository's history and is not detected | None planned; `--changed-since` compares one repository's history |
| `<textarea>`, `<search>` and `<source>` block lines mark coverage incomplete | Such a bundle compares as unknown and needs a rerun or a closed scope | Rewrite the line, or accept the rerun |
| Link syntax inside an HTML block is still governed | A helper named only inside raw HTML is a dependency although CommonMark renders no link | Accept; over-reporting is the safe direction |
| Code spans are masked before links are parsed, as at 1.8.0 | A crafted title or definition destination that crosses a code span can absorb a later real link while coverage stays complete. HTML blocks no longer add the lazy-continuation uncertainty that happened to cover some list forms of this | Parse titles and destinations against unmasked text, or mark such spans incomplete; reported to the owner |
| HTML attributes that span lines or are unquoted are not read | `<a href=helper.py>` names no dependency. Unchanged; raw HTML is not a CommonMark link | Accept, or extend the attribute pattern |
| A non-breaking space inside a tag follows the specification, not markdown-it-py | That renderer accepts it as tag whitespace. Unchanged | Accept |
| A backtick inside an HTML comment still marks coverage incomplete | An existing guard, kept unchanged | Accept |
| Block quotes and lazy continuations keep coverage incomplete | Unchanged by this work | Unchanged |
| Symbolic link tests do not run on Windows | The Windows behavior of the new comparison rests on the code, which only widens selection there | Run them on a Windows host with link privileges |

## Local verification

Run on the final tree in a fresh CPython 3.10.14 environment on macOS arm64,
after `python -m pip install -c constraints-dev.txt -e '.[dev]'`. The imported
package path was checked to be this checkout's `src/tracemantle`.

| Command | Result |
|---|---|
| `make verify-release` | Exit 0. Ruff and strict mypy clean; **1995 passed, 3 skipped, 95.76% coverage** against the 80% floor; self-host skill validated; 1.9.0 wheel and source archive built and passed the clean-install checks of `scripts/verify_artifacts.py` |
| `python scripts/generate_reference.py --check` | Exit 0 |
| `python scripts/check_changelog_release.py 1.9.0` | Ready to release |
| `python docs/verification/correctness-trust-closeout/reproduce.py` | [reproduce-after.jsonl](reproduce-after.jsonl) |

The three skips are environmental: the isolated producer test needs Linux
tooling, the minisign test needs `minisign`, and the offline tokenizer test
needs the optional `tiktoken` extra. The symbolic link tests ran. An earlier
`make verify-release` on this branch stopped at its last step because
`candidate-dist` still held the 1.8.0 artifacts beside the new ones; they were
moved out and the gate was rerun in full.

Not run locally: Linux, Windows, Python 3.11 to 3.15, the `tiktoken` lanes and
the signature and producer job. Remote CI on the pull request is the evidence
for those. `test_link_dependencies.py` and `test_changed_since.py` hold the
regression tests; the files in this directory hold the before and after runs.
