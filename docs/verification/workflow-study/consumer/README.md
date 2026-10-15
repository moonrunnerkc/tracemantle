# Reproduce the SARIF deployment study

Read [the case study](case-study.md), [frozen protocol](protocol.md), and
[measurement amendment](amendment-2.md). `summary.json` contains absolute counts,
per-case outcomes and all three timing repetitions. The two compressed result
archives contain machine-readable runs, decisions, raw logs, source pins and
SHA-256 indexes. Version 2 additionally contains each trusted Git repository as a
Git bundle; clone it and verify the revision/policy digest recorded in the decision.
No credentials or private scanner inputs are included. Temporary absolute paths
are retained; no substantive inputs were redacted. Live traces include the
licensed upstream skill text; the vendor license/provenance applies.

From this branch, with Linux CPython 3.12.3, Git, jq 1.7 and network access for
constrained Python package installation, run this single command with a new
external directory:

```sh
bash scripts/reproduce_sarif_study.sh /tmp/sarif-reproduction
```

It clones a clean checkout of the exact measurement commit, creates a fresh
virtual environment, installs pinned dependencies, measures a new seed approval,
and repeats all 66 trials. It checks complete arm agreement and zero reuses.
Each current seed is a new measured approval; original timestamps and Git commit
IDs are not forged. Runtime, temporary paths, approval revisions and artifact
hashes will differ. The original event artifacts are retained for historical
verification. Do not reuse the October seed as fresh evidence after expiry.

After dependencies are installed, seed/evaluate commands in the script are
**offline**: scanner, helper, jq, comparison and reference execution require no
model or network access. Offline archive inspection/reproduction can use an
already prepared environment with those exact package versions. The environment
record lists the measured versions. Model observations require authorized Codex
access and are **not** part of the reproduction command. The three-call live
budget was consumed; `live.tar.gz` preserves those events and answers.

The protocol incorrectly transcribed jq as 1.6. The measured executable was
jq 1.7, established by direct version output, and its actual binary digest was
already included in the frozen seed's configuration identity. This correction
does not change any result or compatibility decision. The machine hashes, not
the mistaken prose version, identify the executed tool.

Reproduction was verified from `/tmp/sarif-clean-reproduction`, with a new clone
and venv: all 66 trials completed, every arm agreed, and no check was reused.
That verification consumed additional resources; see `verification.json`.
