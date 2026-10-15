# Validation and evidence workflow handoff

## Source and scope

Started on clean `main` at `a5c02e9d7101da85665e75eec471d7dc92bbd4f8`, equal
to fetched `origin/main`. The prompt's `8745c6f` baseline was two commits older;
the tilde-reference fixes were retained. Final HEAD is unchanged; the deliverable
is an uncommitted local diff plus new files, identified by [source.json](source.json).
No push, merge, publication, workflow enablement or protection change occurred.
The global and repository instructions were read; no nested instruction files
were found. Repository policy and the existing ignored local CLAUDE copy remain
synchronized. No unrelated dirty work existed at the start.

The [preimplementation checklist/design](../../automation-design.md) distinguished
existing capabilities, usability work and intentional protections. No production
bug was inferred from the request. These are feature and usability regressions;
no claim is made that they reproduced a defect on the starting implementation.

## Acceptance and risks

| Area/risk | Status and evidence |
| --- | --- |
| First validation requires advanced setup | Already unnecessary; help now groups common/advanced options. Six real CLI cases and JSON gates in `tests/test_onboarding.py`; identical published/built transcripts linked below. |
| Per-run digest commits | Removed only for explicit schema-2 authority. `policy.py`, `approvals.py`, `comparison.py`, `product_commands.py`; two changed bundles pass one unchanged base/policy using real OpenSSH signatures. |
| Legacy trust accidentally broadened | Preserved. Schema 1 and disabled schema 2 reject unapproved records; manual approval passes; `required_signers` remains additional on either route. |
| Candidate policy/checker/adapter or tooling substitution | Immutable Git policy/checker and scoped authority preserved; candidate bytes remain data. Reference observer executes only a sandboxed helper, takes checker/configuration/fixture/profile from Git and uses a trusted installed adapter. Candidate or trust-worktree replacements cannot choose comparison authority. |
| Wrong signer, unlisted/revoked key, changed record | Signed negative controls reject all. Key removal applies at a newly selected trusted base; old immutable bases retain their authority. |
| Wrong bundle/check/policy/run; replay/expiry | Approval binds all subjects and protected run ID/start, and enforces lifetime. Cross-run replay fails; same-run repeated verification is intentional. No consumption database. |
| Missing tools, malformed keys/approvals, unsupported policy | Fail closed with actionable infrastructure errors; no weaker approval fallback. Size/duplicate/numeric errors tested. |
| Signing arbitrary candidate claims | Producer constructs its own record from isolated execution and trusted checker output, validates compatibility, then signs. Key/host-secret absence tested inside candidate sandbox. Failed checker produces no approval. |
| Missing/unknown/skipped/incompatible/conflicting evidence | Existing gate semantics retained and exercised with signed records. Complete record digest authenticates identity, outcome and context. |
| Model aliases promoted to fresh execution | No current-run exception introduced; immutable-model restrictions remain even for automation-approved records. |
| Helper/dependency changes | Existing transitive trusted-Git regressions retained; signed old candidate approval rejects a helper-only change, and a fresh observation of the new bundle passes. |
| Evaluator lock-in | `adapters/neutral.py` accepts complete records through bounded data-only JSON; original source and importer identity retained. No custom code required. |
| Promptfoo version/grading drift | 0.118.10 unchanged; exact 0.124.1/results-v3 subset verified with unmodified npm-generated pass/assertion/error exports and upstream release source. Provenance distinguishes local deterministic exports from upstream-authored results. Unknown shapes direct users to neutral import. |
| Partial writes or embedded code | Malformed second records, mismatched bundles, duplicate keys, overflow and oversized sources fail before writes. Neutral/Promptfoo providers and assertions are never executed by import. |

The 45-case automation module, 11 neutral cases, 16 current-Promptfoo cases and
8 onboarding cases add 80 collected cases. Existing behavioral, dependency,
CLI, signature and compatibility tests remain. The self-host golden changed
only output-node line numbers/derived IDs after adding four documentation lines;
no functional assertions or coverage gates were weakened.

## Commands and measured workflow effort

Basic validation remains:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install tracemantle==1.6.1
tracemantle hello/SKILL.md
tracemantle skills/ --strict --format json
```

Use your actual skill path, or copy the [first skill](../../getting-started.md#validate-your-first-skill).
The [six exact command/output transcripts](onboarding-published.json) match the
[built wheel transcripts](onboarding-built.json), including error and strict exits.

For automation use the unreleased built package and the
[runnable setup and two-run commands](../../evidence-workflow.md#runnable-isolated-producer-and-verifier).
The recurring producer/verifier commands are:

```bash
RECORD=$(python -I "$DEMO/trusted/producer.py" run "$DEMO" \
  --base-revision "$BASE" --run-id "$RUN_ID" --run-started-at "$START")
tracemantle compare "$DEMO/baseline/demo" "$DEMO/candidate/demo" \
  --trusted-root "$DEMO/trusted" --base-revision "$BASE" --evidence "$RECORD" \
  --approval-run-id "$RUN_ID" --approval-run-started-at "$START"
```

`BASE` is owner-selected and immutable; `RUN_ID`/`START` come from the protected
scheduler. [Installed acceptance](installed-evidence.json) records concrete paths,
IDs, commands, outcomes and the unchanged base for both runs. Local invocation is
manual in this demonstration; once scheduled, it needs no per-run approval action.

Count units explicitly: a setup responsibility is one owner-reviewed installation,
configuration or isolation decision; a recurring approval action is review or
policy modification after evidence exists. Common evaluation/import/compare
execution is excluded from approval-action counts, but shown above.

| Demonstrated workflow | Before | After |
| --- | --- | --- |
| Basic setup shell commands: venv, activation, install | 3 | 3 |
| Basic recurring check commands | 1 | 1 |
| Basic evidence setup/approval/commits | 0 | 0 |
| Evidence one-time responsibilities: trusted toolchain, check+fixture/context policy, observer isolation, approval key custody | 3 without signing (first three) | 4 (adds scoped key custody) |
| Initial trusted policy commit | 1 | 1 |
| Recurring manual approval actions per run: review record, add/commit digest | 2 | 0 |
| Policy/evidence approval commits for two changed bundles | 2 | 0 |
| Per-run evaluation/import/compare work | Required | Still required; observer groups execution/import/approval in one producer invocation |

Automation reduces recurring approval work, not initial trust responsibilities.
A bot committing digests is not used. The example does not deploy a scheduler or
change protections. A production owner must approve and protect those components.

## Verification and editorial walkthrough

- `ruff check src tests scripts`, strict `mypy` (79 source files), and
  `python scripts/generate_reference.py --check`: passed. Ruff and mypy also
  passed on both new executable example scripts. `git diff --check`: passed.
- [Python 3.12.3, no tiktoken, `make verify-release`](verify-release.txt):
  **1,530 passed, 5 skipped, 88.92% coverage**. Four skips are the Python 3.10-only
  TOML fallback; the fifth was absent minisign. The gate also passed self-host
  symbolic/graph validation, wheel/source build and clean installs.
- [Python 3.12.3 with tiktoken 0.14.0 and minisign 0.11](tokenizer-python312.txt),
  `python -m pytest tests/ --cov-fail-under=80`: **1,531 passed, 4 skipped,
  88.92% coverage**. All skips are the existing 3.10-only cases. This matches the
  optional-tokenizer job's full-suite command; [calibration](calibration.json)
  and [reference conformance](conformance.json) also passed.
- [Python 3.10.21 focused boundary/onboarding/tokenizer checks](python310-focused.txt):
  **125 passed**, including TOML fallback, OpenSSH/minisign, both import routes,
  and protected producer/verifier. This was a focused run with `--no-cov`, not
  a full 3.10 suite. [Clean wheel/source checks on 3.10](artifacts-python310.json)
  passed. A uv-created environment initially failed nested copied-venv bootstrap;
  running the unchanged artifact verifier with the managed base interpreter
  resolved that environment issue. No product fallback was added.
- Clean published 1.6.1 and built wheel installs outside the checkout produced
  identical six-command onboarding transcripts. The clean built package completed
  the neutral-export/import and two-run producer/verifier walkthrough, including
  stale-bundle, disabled-authority and manual-approval controls.
- The initial full run exposed three local integration issues: missing activated
  PATH for pre-commit, the relocated count check, and tutorial fixtures outside
  the established fixtures tree. All were corrected; the seven focused checks
  and final full suites passed. No functional assertion was weakened.
- Final documentation/artifact refresh is recorded in [artifacts-final.json](artifacts-final.json).
  Runtime sources and tests are unchanged from the passing gates. No legacy
  SkillCheck distribution uninstall/reinstall migration was requested or run;
  clean artifact checks exercised the deprecated import compatibility surface.
- Remote CI, macOS, Windows, Python 3.11/3.13 full suites, a production hosted
  signing workflow and live agent evaluation were not run. Existing remote run
  records apply to earlier commits, not this local diff.

The README is **306 whitespace-delimited words**, four sections beneath its title.
Editorial first-reader walkthrough: the first two sentences state the file-checking
job and optional reuse task; the first code block creates an environment, installs
published 1.6.1 and runs validation; the next block shows authentic output and
explains the heuristic score; the five task links lead to first-file creation, CI,
evidence, reference and troubleshooting. All 56 local links/anchors checked across
the touched task/contract guides resolve. Referenced upstream source pages returned
HTTP 200. This is an editorial and execution check, not a human usability study.

## Compatibility and remaining boundaries

No runtime dependency, default validator behavior, public top-level API, config
precedence, JSON envelope, exit code or strict-mode rule changed. External Python
adapters still execute explicitly selected trusted code with caller privileges.
Schema 2 is opt-in; schema 1 and additional record signatures retain their meaning.
Disable automation by removing its table at a new selected trusted base. Old policy
versions reject the new authority rather than interpreting it loosely.

The package remains unreleased development source reporting version 1.6.1; the
README's published-package commands intentionally use released behavior. Package
publication is not authorized and remote CI on this local diff has not run.
Linux checks do not establish macOS/Windows or the complete Python CI matrix.
The protected producer requires Linux bubblewrap, trusted host/runtime/toolchain,
secure keys and nonreused scheduler run identity. No hosted production deployment
or real agent/model evaluation occurred. Promptfoo tests used local echo/error
providers. Adoption, trust, stars, time saved and live-agent reliability remain
unmeasured. A future release needs an owner-selected version and exact-source CI,
followed by separate explicit publication authorization.
