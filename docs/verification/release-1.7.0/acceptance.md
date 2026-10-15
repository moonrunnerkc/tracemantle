# 1.7.0 release verification

## Recovery and release preparation

The owner authorized commit, push, normal merge, stable publication and restoration
of publishing controls. Recovered the existing dirty `main` worktree at
`a5c02e9d7101da85665e75eec471d7dc92bbd4f8`; fetched upstream was identical.
No unrelated changes were present. Before metadata edits, every file digest in
[the implementation manifest](../usability-evidence/source.json) matched and its
canonical manifest digest was
`d203260bb2033485fc55ba72da0a0f4b7a5a4ad835af49c2ec46a79b1c1ecb72`.
That historical manifest identifies the pre-release implementation, not 1.7.0.

GitHub and live PyPI API queries found 1.6.1 latest, with no 1.7.0 version or tag.
The backward-compatible opt-in additions warrant minor version 1.7.0. Package,
API, installed skill, lock metadata and active installation/Action/pre-commit
examples were synchronized; historical verification records were retained.
The changelog was fully promoted before tagging and the release checker passed.
A temporary Git test confirmed release-note automation leaves newer main entries
untouched when the released tag already contains its version heading.

Review found no committed private keys, accidental credential material, weakened
trust checks or runtime dependency changes. Test keys are generated in temporary
directories. The CI approval job now installs its system tools and fails if any
signature/producer test skips; it also runs the Action from the checked-out source.
The implementation's signed deterministic helper tests are workflow mechanics,
not a real agent evaluation or a production signing deployment.

The README is 305 whitespace-delimited words. Its first command block installs
1.7.0, validates one file and links the first-file example. The displayed result
explains heuristic advice and the live-agent limitation. Five task links expose
CI, imports, approval and troubleshooting without requiring them for validation.
This is an editorial walkthrough, not a human usability study.

## Released source and remote gates

**Published 1.7.0** at immutable source
`f35821830f249df847faf57c0db6e45a50245740`, tag object
`53576a83a084f1ba14597db6207db980af975785`.
[Source manifest](source.json):
`ce2f92795d09f4c3dc1741928ca77c06cb19ee6ae09bad96ff21705922c234e2`.
Its procedure sorts tracked regular files outside `docs/verification/`, records
SHA-256 of original bytes and executable bits, then hashes compact sorted-key
JSON. Reproduce against the release tag, not the later documentation checkout.
Verification files are excluded to avoid circular source identities.

[PR #23](https://github.com/moonrunnerkc/tracemantle/pull/23) merged through the
normal process after all 16 [PR checks](https://github.com/moonrunnerkc/tracemantle/actions/runs/38672399089)
passed. No required reviewer or protection was bypassed. All 16 jobs in
[exact merged-SHA CI](https://github.com/moonrunnerkc/tracemantle/actions/runs/38673240033)
and all 18 jobs in [Release](https://github.com/moonrunnerkc/tracemantle/actions/runs/38674161197)
passed. Each exercised Python 3.10, 3.11, 3.12 and 3.13 on Ubuntu, macOS and
Windows, plus lint, strict typing, generated references, the optional tokenizer,
calibration/conformance, clean artifact installs and the separate approvals job.
[Main CI counts/coverage](main-ci-tests.json) and [tag-run results](release-tests.json)
preserve actual platform results. Main matrix coverage was 88.71–89.04%, above
the unchanged 80% floor. Platform/tool and interpreter-specific skips remain;
the mandatory OpenSSH/minisign/isolated-producer job passed **57 cases, zero
skips**, and executed the Action from the exact tag source.

Final local commands were `ruff check src tests scripts`, `mypy`,
`python scripts/generate_reference.py --check`,
`python scripts/check_changelog_release.py v1.7.0`, and `make verify-release`.
All passed on the final candidate. The latter ran 1,531 tests with four
Python-3.10-only skips on Python 3.12.3 at 88.92% coverage, self-host validation,
builds and clean wheel/source installs. Focused acceptance passed 147 cases.
The final gate used minisign 0.12; earlier 0.11 checks also passed.

Three concrete CI corrections were made before merge:

- Ubuntu 22.04 repositories lacked minisign. Ubuntu 24.04 then rejected the
  producer's user namespace, and the no-skip guard correctly failed. The final
  job uses Ubuntu 22.04, its OpenSSH/bubblewrap packages, and upstream minisign
  0.12 pinned by SHA-256. No host protection was disabled. The failed jobs remain
  visible in [first](https://github.com/moonrunnerkc/tracemantle/actions/runs/38671371627/job/116215027401)
  and [second](https://github.com/moonrunnerkc/tracemantle/actions/runs/38671539999/job/116215556098)
  attempts; superseded runs were canceled to free capacity.
- Windows [exposed](https://github.com/moonrunnerkc/tracemantle/actions/runs/38671724465/job/116216146641)
  POSIX-only transcript expectations and default-decoding assumptions. Tests now
  decode UTF-8 and expect the existing native-path contract; all diagnostic and
  JSON/exit assertions remain. The guide labels native Windows paths.
- Pytest embedded the 65 KiB input into a parameter ID, exceeding Windows'
  environment-variable limit. Short explicit IDs retain the full oversized input
  and rejection assertion. No functional test, input or coverage gate was weakened.

## Public artifacts and installed acceptance

[GitHub release](https://github.com/moonrunnerkc/tracemantle/releases/tag/v1.7.0)
and [PyPI](https://pypi.org/project/tracemantle/1.7.0/) serve the exact quality-job
artifacts. Local, PR, merged-SHA CI, tagged quality, public PyPI and separately
downloaded GitHub assets all match:

| Artifact | SHA-256 |
| --- | --- |
| `tracemantle-1.7.0-py3-none-any.whl` | `7074b85cf9c112da84de04713afddd00c6aafefbdafc6de3f1835f54e54af77c` |
| `tracemantle-1.7.0.tar.gz` | `9eab683d8a0d449e42669a25fb95d3c3cf6bc0e2242e465e65e89b646347c980` |

The release includes matching `SHA256SUMS`. GitHub CLI 2.102.0 verified each build
attestation with repository, signer workflow, source digest and source ref pinned,
and self-hosted runners denied. PyPI publishing attestations were independently
verified with Sigstore policies pinning repository URI, source digest/ref,
`release.yml` build-config URI and certificate identity. [Verification results](pypi-attestations.json)
include the public provenance URLs; [publication.json](publication.json) records
source/tag identities, runs, artifact hashes and controls. The successful trusted
publisher used the existing `tracemantle` project and `pypi` environment.

Four new environments outside the checkout installed the downloaded public wheel
and source archive separately on Python **3.10.21** and **3.12.3**, with caches
disabled, no editable install and no source-path injection. Each passed `pip check`,
CLI/API/metadata version checks, and **147 installed acceptance cases with zero
skips**. [Installed results](installed.json) identify each artifact/environment.
Tests and fixtures came from the public source archive; only `tests/`, `docs/`
and README were copied into the test working directory, never `src/`. Isolated
Python imports confirmed the package came from the environment's site-packages.
Source installs built anew with constrained Hatchling and no wheel cache.

The executed installed-suite selection was:

```bash
python -m pytest -c /dev/null --no-cov -q \
  tests/test_signatures.py tests/test_automation_approvals.py \
  tests/test_neutral_import.py tests/test_promptfoo_current.py \
  tests/test_onboarding.py tests/test_build_plan_product.py
```

This covers legacy digest approval, schema-2 success and rejection controls,
real signatures and two changed bundles without recurring digest commits,
helper invalidation, neutral JSON, both supported Promptfoo contracts,
malformed/oversized inputs and CLI/JSON/exit behavior. A fifth fresh environment
used the README's public install command:

```bash
python -m pip install tracemantle==1.7.0
tracemantle hello/SKILL.md
```

All six onboarding text outputs and JSON/exit contracts passed, including invalid
frontmatter, missing helper, directory scan and warning/strict behavior. Exact
commands and output are in [onboarding-public.json](onboarding-public.json).
This verifies the published new features independently of the earlier 1.6.1
basic-output comparison. The source archive includes the examples, documentation,
installed skill and authentic upstream fixtures; the wheel contains the runtime
adapters, approval implementation, schemas, profiles and entry points.

## Restored controls and remaining scope

The workflow moved `v1` to the same released commit. Both the immutable tag and
moving major tag were checked remotely. After the release settled, the monitor
restored `TRACEMANTLE_PUBLISH_ENABLED=false` and disabled Release; both states
were independently reread before subsequent installation checks. No environment
restriction or repository protection changed. [Release notes automation](https://github.com/moonrunnerkc/tracemantle/actions/runs/38675186274)
passed and recognized the pre-promoted changelog without another promotion PR.

This verification record lands after publication. Its documentation commit and
CI are distinct from the immutable release source; neither tag nor shipped bytes
move with it. Historical implementation records retain their original source
identities and measurements. No new package release is implied by that follow-up.

No real agent/model evaluation or production signing deployment occurred. The
protected automation example and Promptfoo echo/error providers test deterministic
mechanics. Hashes identify content, signatures identify an approving key holder,
and execution claims still depend on the trusted observer and environment.
Adoption, user trust and live-agent reliability remain unmeasured. No package,
public-install, platform-matrix or publishing-control blocker remains.
