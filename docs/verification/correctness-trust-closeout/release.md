# 1.9.0 release record

Delivery of the two corrections in [acceptance.md](acceptance.md). The owner
authorized the merge and this one release on 2026-11-24. This file was
written after publication; its commit is later than the released source and
moves no tag.

## Source and remote gates

| | |
|---|---|
| Pull request | [#33](https://github.com/moonrunnerkc/tracemantle/pull/33), tested head `a08eb43c7d1edbcd86fe19b8335c6a9626eedfa0` |
| Head checks | 30 of 30 succeeded, none skipped: [CI run 45538555683](https://github.com/moonrunnerkc/tracemantle/actions/runs/45538555683) with the `CI gate`, and the [pull request verifier](https://github.com/moonrunnerkc/tracemantle/actions/runs/45538555569) |
| Merge commit | `b7a7e1e6d36505f8e28c1b785a4a2910936f4216`, merged through the protected pull request route |
| Merge commit CI | [run 45540499571](https://github.com/moonrunnerkc/tracemantle/actions/runs/45540499571): 29 of 29 jobs succeeded, covering Linux, macOS and Windows on Python 3.10 to 3.15, the tokenizer lanes, approvals, package, artifact installs and audits |
| Tag | `v1.9.0`, annotated tag object `dac19db5e01ded8cc7cdddbbb23d7fd6c827fd00`, target `b7a7e1e6d36505f8e28c1b785a4a2910936f4216`. Created only after the merge commit's CI succeeded |
| Release workflow | [run 45542207680](https://github.com/moonrunnerkc/tracemantle/actions/runs/45542207680): 31 of 31 jobs succeeded, including the repeated quality gate, `release` and `move-major-tag` |

An earlier head of the pull request, `611f0eb`, passed the `CI gate` but left
the verifier incomplete: a script added under this directory introduced three
findings in a whole-repository lint run. The script was corrected in
`a08eb43` and every check was rerun on that head. Nothing was bypassed.

Version 1.9.0 was unused in package metadata, tags, GitHub releases and PyPI
before tagging. It is a minor release because it also carries the `--strict`
change and the other entries that had accumulated under Unreleased. `v1.8.0`
still identifies `5026e8e83f66c6addcdf45fb68f559f3e05b6a0e`.

## Published artifacts

| File | SHA-256 |
|---|---|
| `tracemantle-1.9.0-py3-none-any.whl` | `81786d3e6f246ff7d30d4388f4c43546960eebeb97f4b4d4139694ad9f2c5cd4` |
| `tracemantle-1.9.0.tar.gz` | `644ba13cad35674a724b1b75b84f26bef9916259801ccc2bdc5699182cde9242` |

- [PyPI 1.9.0](https://pypi.org/project/tracemantle/1.9.0/), uploaded by the
  workflow through trusted publishing. Both files were downloaded from PyPI
  and hashed; the digests match the PyPI JSON API.
- `gh attestation verify FILE --repo moonrunnerkc/tracemantle --source-digest b7a7e1e6d36505f8e28c1b785a4a2910936f4216 --source-ref refs/tags/v1.9.0`
  exited 0 for both downloaded files. The certificates name
  `.github/workflows/release.yml@refs/tags/v1.9.0`.
- PyPI's integrity API returns one publish attestation per file, with
  publisher `moonrunnerkc/tracemantle`, workflow `release.yml`, environment
  `pypi`.
- [GitHub release v1.9.0](https://github.com/moonrunnerkc/tracemantle/releases/tag/v1.9.0)
  is published and Latest. Its notes are the `[1.9.0]` changelog section of
  the tagged source. Like 1.8.0 it carries no uploaded assets.
- The workflow moved `v1` to `b7a7e1e6d36505f8e28c1b785a4a2910936f4216`, read
  back from the remote.
- [Release notes automation](https://github.com/moonrunnerkc/tracemantle/actions/runs/45544555722)
  succeeded with "[1.9.0] was recorded before tagging; nothing to promote" and
  opened no pull request.

## Installed distribution

A new CPython 3.12.13 environment outside the checkout, with
`python -m pip install --no-cache-dir tracemantle==1.9.0` and no editable
install or path override. The module loaded from that environment's
`site-packages`, the installer was `pip` and there was no `direct_url.json`.
The fixture builders come from this checkout's `tests/`; the CLI under test
is the installed distribution. The first install attempt, seconds after the
upload, found no 1.9.0 on the index; the rerun 45 seconds later succeeded.

- [published-install-1.9.0.txt](published-install-1.9.0.txt): `pip check`
  clean, CLI and module report 1.9.0, the README quick start passes with exit
  0, the three HTML block bodies report the helper edge and compare as
  `unknown` with exit 4 and rerun `validate`, and the symlinked configuration
  cases check 1 file and exit 1 in the unstaged, staged and committed states.
- [published-install-1.8.0.txt](published-install-1.8.0.txt): the same
  script against the published 1.8.0 still shows both false passes. On 1.8.0
  the `--config` row also selects nothing, because that release predates the
  configuration change detection added after it.

Only macOS was used for this installed check. Windows PowerShell commands in
the README were not executed.

## Restored controls and read-back

Read through the GitHub API after the release, not from checked-in files:

| Control | State |
|---|---|
| `TRACEMANTLE_PUBLISH_ENABLED` | `false`, set 2026-11-25T04:05:44Z; it was `true` from 03:45:50Z |
| Release workflow | `disabled_manually` |
| Ruleset "main: pull request and CI gate" | active, no bypass actors; deletion, non-fast-forward, pull request and required `CI gate` |
| Ruleset "version tags are immutable" | active, no bypass actors; deletion and update blocked for `refs/tags/v*.*.*`. Not exercised by attempting a mutation |
| `pypi` environment | deployment restricted to `v*.*.*` tags |
| Private vulnerability reporting | enabled |

No protection, credential, environment rule or account setting was changed.
The four open Dependabot pull requests were left untouched.

## Not established

No agent runtime loaded a skill and no model ran; compatibility profiles
remain unverified. The retained limits in [acceptance.md](acceptance.md)
apply to 1.9.0.
