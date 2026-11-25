# Follow-up: retained limits of the 1.9.0 closeout

The [closeout](acceptance.md) and [release record](release.md) listed limits
that 1.9.0 kept. The owner asked on 2026-11-24 for the rest to be resolved at
their cause, leaving Windows aside. This record covers that work. It is on
`main` after 1.9.0 and is not in a published release.

Starting point: `v1.9.0` (`b7a7e1e6d36505f8e28c1b785a4a2910936f4216`). Local
environment: macOS 26.7.3 arm64, CPython 3.10.14, Git 2.54.0. Renderers used
as oracles, in a separate CPython 3.12 environment: markdown-it-py 4.0.0 in
CommonMark mode, cmark-gfm through `cmarkgfm`, and commonmark.py. None is a
dependency of the package. No skill content, helper or model was executed.

## Outcome by limit

| Limit after 1.9.0 | Outcome | Evidence |
|---|---|---|
| Code spans were blanked before links were parsed, so a title or definition could absorb a later link while coverage stayed complete | Resolved. Spans and links are read in one left-to-right pass | `test_code_spans_and_links_bind_left_to_right`, `test_a_title_cannot_absorb_a_link_across_a_code_span`; inline differential run |
| A multi-hop configuration link was validated on every incremental run | Resolved. Each hop is checked against Git history | `test_an_unchanged_link_chain_is_shown_unchanged_hop_by_hop` |
| An external configuration link was validated on every run | Resolved where history exists: a target in another repository is compared there. A target in no repository has no baseline, so selecting its skills is the correct result, not a shortcut | `test_a_link_into_another_repository_is_compared_with_that_repository`; the external case of `test_symlinked_configuration_that_cannot_be_shown_unchanged_selects_its_skills` |
| `<textarea>`, `<search>`, `<source>` and lowercase declarations marked coverage incomplete | Resolved. Every recognized reading is tokenized and governed, and coverage stays complete | `test_html_forms_that_renderers_read_differently_govern_every_reading`; block differential run |
| A blank line inside a comment or `<pre>`-style block within a list item marked coverage incomplete | Resolved the same way | Same test |
| A Setext underline after definitions marked coverage incomplete | Resolved exactly for `=`; a line of hyphens has two renderer readings and both are governed | `test_a_setext_underline_after_definitions_is_resolved_exactly` |
| A link into a directory through `name/..` could not be shown unchanged | Resolved when `name` has committed content at the revision; otherwise Git records nothing about it and the skills are selected | `test_an_unchanged_link_chain_is_shown_unchanged_hop_by_hop`, `test_link_text_that_depends_on_an_untracked_directory_is_not_shown_unchanged` |
| A directory link on a `--config` path that resolves to the repository root was treated as spelling | Resolved. Only a link kept outside every repository is treated that way | `test_explicit_configuration_through_a_tracked_link_to_the_repository_root_is_not_shown_unchanged` |
| Stale artifacts in `candidate-dist` stopped `make verify-release` | Resolved. The target empties the directory before building | A marker file placed there was gone after the gate ran |
| Merged feature branches remained on the remote | Resolved. The three branches of this work were deleted after confirming they are in `main` | `git branch -r` |
| Symbolic link tests do not run on Windows | Not addressed, as instructed | |
| No agent runtime loaded a skill; compatibility profiles are unverified | Not resolved and not attempted. See below | |

### Found while resolving these

The differential runs exposed further disagreements between renderers. Each
could hide a link under one renderer while coverage stayed complete at 1.9.0,
and each is now governed:

- A backslash before a space kept the space in a destination, which CommonMark
  does not. The CommonMark reading is parsed first and the older reading is
  still governed.
- markdown-it closes the paragraph after a complete definition and cmark
  continues it, which changes what an HTML tag line or an indented line after
  it is.
- commonmark.py and markdown-it reject a definition with an empty title and
  render its line as text. Link syntax inside a definition is now governed.
- markdown-it and cmark can read a code span's delimiters as literal text
  when the paragraph also holds an unclosed backtick run.

## Before and after

- [followup-tokenizer-before.txt](followup-tokenizer-before.txt) and
  [followup-linked-config-before.txt](followup-linked-config-before.txt): the
  tests of this change run against the 1.9.0 source. 21 and 9 fail. Three of
  the 9 fail only because the stderr wording changed.
- [followup-differential.txt](followup-differential.txt), produced by
  [differential_html_blocks.py](differential_html_blocks.py) and
  [differential_inline.py](differential_inline.py). A document counts as
  missed for a renderer when that renderer produces a `helper.py` link that
  the tokenizer neither reports nor marks incomplete.

| Run | Documents | markdown-it-py | cmark-gfm | commonmark.py |
|---|---|---|---|---|
| Block structure, 1.9.0 | 300,000 | 1 | 1 | 0 |
| Block structure, this change | 900,000 | 0 | 0 | 0 |
| Inline precedence, 1.9.0 | 400,000 | 13 | 9 | 9 |
| Inline precedence, this change | 1,200,000 | 1 | 0 | 0 |

The one remaining document is listed at the end of that file. It has three
interleaved backtick runs of two lengths around a link destination, and only
markdown-it-py renders its link. The literal-backtick reading is an
approximation of that renderer, and this is where it falls short.

These runs search chosen vocabularies. They are evidence, not a proof, and
the script files in this directory now hold the vocabularies of this run,
which are larger than the ones used for the 1.9.0 record.

## Cost

Every input stays linear. [followup-timing.json](followup-timing.json),
produced by [followup_timing.py](followup_timing.py), holds seconds at two
sizes for 1.9.0 and for this change. The timings were taken on a shared
machine and vary between runs by up to a factor of two; the doubling from
200,000 to 400,000 units is the property that matters.

| Input, 400,000 units | 1.9.0 | This change | Why |
|---|---|---|---|
| Definition lines | 2.0 s | 3.0 s | Link syntax inside definitions is read |
| Definitions each followed by a tag line | 4.1 s | 15.8 s | Two readings of every paragraph |
| Three divergent tags and 400,000 link lines | 1.8 s | 15.1 s | Eight readings |
| Unclosed spans | 0.08 s | 0.13 s | |

A document tokenizes once unless it contains one of the divergent forms.
The eight-reading bound caps the multiplier.

## Limits that remain

| Limit | Practical effect | Next step |
|---|---|---|
| Runtime compatibility profiles are unverified | `compat.*` notes are historical advice. Resolving this needs an observation of VS Code and Cursor loading a skill, with the runtime version pinned, recorded in `verified.toml` by the checklist in `docs/profiles.md`. Cursor is not installed on this machine, VS Code's agent needs an interactive signed-in session, and no model session was started | The owner records a pinned-runtime observation |
| A configuration link whose target is in no Git repository is validated on every run | Correct: no baseline exists. It costs selectivity only | Keep the target in a repository |
| More than eight readings, or a definition longer than 16 lines in a paragraph of definitions, marks coverage incomplete | Bounds on work for crafted input | None planned |
| The literal-backtick reading approximates markdown-it and cmark | One document in 1,200,000 of the inline run is still missed for markdown-it-py | Emulate that renderer's backtick cache if it matters |
| Inline HTML, autolinks, block quotes and lazy continuations are not parsed | A backtick inside an inline tag or comment, a block quote, and a lazy continuation still mark coverage incomplete, as before 1.9.0 | A full inline HTML and container parser |
| Link syntax inside an HTML block or a definition is governed | A helper named only there is a dependency although CommonMark renders no link. This is the safe direction and is deliberate | None |
| Symbolic link tests skip on Windows | Unchanged | A Windows host with link privileges |

## Verification

Run on the final tree in a fresh CPython 3.10.14 environment after
`python -m pip install -c constraints-dev.txt -e '.[dev]'`; the imported
package path was this checkout's `src/tracemantle`.

| Command | Result |
|---|---|
| `make verify-release` | Exit 0. Ruff and strict mypy clean; **2036 passed, 3 skipped, 95.65% coverage**; self-host skill validated; wheel and source archive built and passed the clean-install checks |
| `python scripts/generate_reference.py --check` | Exit 0 |

The three skips are the Linux-only producer test, the minisign test and the
optional tokenizer test. Linux, Windows and Python 3.11 to 3.15 were not run
locally; remote CI on the pull request covers them.
