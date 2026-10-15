# Workflow-value study: inconclusive preparation result

No qualifying deployment was completed. No change cases were scored and no
reruns were avoided. The useful result is a reproducible readiness check and a
concrete compatibility barrier on a maintained public skill. This is neither
customer adoption nor an independent external audit.

TraceMantle under evaluation: **1.7.0**, commit
`721845b35ef450ebaaf4c7bfb20990db92d0ed3c`. The
[admission/preparation protocol](protocol.md) was committed as
`192cfb6d11f3fbf568da16b1ace484fdfead6287` before verification runs. It explicitly
forbids scoring before a consumer-specific supplement. No implementation, policy,
assertion, reference check, or existing fixture was changed to improve results.

## Selection and the public-source extension

The [local inventory](local-discovery.json) scanned 51 directories under
`/home/brad/projects`, including this study worktree, hidden directories and
ignored files, excluding dependencies and test-fixture directories. The 71
matched paths include duplicate run worktrees and copied upstream repositories.
The three swarm skills were last changed in March in the two April checkouts;
the maintained project explicitly deleted them in commit
`58bd6a1cf4fd9650867b10e37304147e840a0181` in May. Existing local changes were
preserved. SkillCheck is TraceMantle's earlier checkout, not another consumer.
TraceMantle's self-host skill is one file without packaged helpers; its retained
graph/critique fixtures do not supply independently checked live-agent outputs.
Synced personal skills did not establish a versioned consumer workflow.

[Remote discovery](discovery.json) covered 54 owner-controlled non-fork
repositories returned by the authenticated repository listing. All 18 public
trees and 33 of 36 private trees were inspected without truncation; three private
tree reads failed and are explicitly not absence evidence. No current qualifying
consumer was established. Private repository names, revisions and paths are
redacted; their inventories cannot be independently reconstructed from this report.
This is not a claim to have inspected every branch or inaccessible project.

The owner then suggested a public GitHub repository. Candidate inspection covered
`anthropics/skills`, `magnus919/agent-skills`, and `trailofbits/skills`. The latter
was selected for an **exploratory probe** because its actual SARIF skill has Python
helpers, linked Markdown, retained scanner-format fixtures, and upstream tests
that execute both the helper and documented jq commands. The reference assertions
come from that project and do not use TraceMantle's decision logic.

Pinned source:
[trailofbits/skills at 1f68e03](https://github.com/trailofbits/skills/tree/1f68e03536f7980d4c0e6869596f708043a19443),
`plugins/static-analysis/skills/sarif-parsing`. The account has read access and no
push/maintain permission. The source was fetched without modifying tracked files.
This public-source probe does not supersede the requirement that a copied public
repository alone is insufficient evidence of an actual deployment. No upstream
contact, installation into an active consumer, PR, or adoption is claimed.

## What the probe established

The upstream metadata validator ran across **44 plugins**, resolved **522
references**, and reported zero errors and seven line-count warnings. Its self-test
passed. The upstream interface validator checked **74 interfaces** and passed.
All **24 SARIF tests passed**, including tests that run the documented jq severity
gate and distinguish equal basenames in different directories. These are real
helper/documentation tests, not live agent execution or consumer production runs.

TraceMantle's default validation nevertheless exited **1** on that unchanged
skill, with four reference errors:

| Location in the pinned skill | Diagnostic | Independent interpretation |
| --- | --- | --- |
| Line 91: `/path/to/project/`, `/github/workspace/` | `references.escape` | Examples explaining scanner path differences, not files to load |
| Lines 262–263: `auth/login.py`, `admin/login.py` | `references.broken-link` | Examples explaining why deduplication must retain directories |

The [original output](public-probe/logs/tracemantle-validation.stdout.txt) retains
the advisory fields, two warnings, and all four errors. The
[manifest](public-probe/logs/tracemantle-manifest.stdout.txt) exited **4**, reported
incomplete dependency coverage, and cannot justify reuse. The source also uses
`{baseDir}` templates, which are outside TraceMantle's supported static path subset.

This is an observed integration mismatch with an explanatory example, not a
newly found production defect in the skill. TraceMantle's documented contract
classifies standalone path-like inline code as resource candidates. Changing that
rule to exempt these four strings would hide genuine missing-resource failures.
No such exception, dependency deletion, `--skip-ref-check`, or false declaration
of complete coverage was introduced. A gate enabled unchanged on this skill would
block the setup revision despite the independently passing checks. This was
exploration, so it is not counted as a scored unnecessary block.

## Measurements and limits

[Machine-readable results](results.json) distinguish zeros from unavailable
measurements. There are **0 scored revisions, 0 proposed skips, 0 verified skips,
and 0 avoided executions**. Mistake detection, missed failures, false-block rates,
and operational savings are unmeasured. No synthetic change history or fabricated
evidence was added to fill those denominators.

The public setup probe consumed **4.08 seconds** end to end. Within that run,
TraceMantle validation consumed **0.114 seconds** and manifest generation
**0.115 seconds**. These are single-run subprocess elapsed times, not comparative
workflow overhead or a speed benchmark. Upstream metadata, interface validation,
and the helper suite took 1.216, 0.114 and 0.265 seconds respectively. The full
consumer CI suite, A/B/C comparisons, repeated change cases, and trust/context
fault matrix were not run. These selected checks do not establish all upstream CI.

TraceMantle preparation consumed **406.50 seconds** for clean checkouts, fresh
environments, dependency installation and checks. Discovery also consumed time;
only the remote tree scan's 17.95 seconds was separately instrumented. Total
authoring/review/setup time was not measured. All of this is research overhead,
not operational savings. The evaluated runs made **0 model calls**, used **0 model
tokens**, and incurred **$0 evaluation API charges**. This authoring agent's tokens,
cost, human intervention time and CI monetary cost are unavailable. No human hours
saved are inferred.

No behavioral benefit is claimed. TraceMantle rejects historical reuse of mutable
hosted model aliases, including records for an equal bundle. Its existing tests
use synthetic records or deterministic helper stand-ins; they do not prove live
agent reliability. No immutable model revision was invented for this study.

## Verification actually performed

Fresh Linux CPython 3.12 environments at the original revision:

| Environment | Actual result | Coverage |
| --- | --- | --- |
| Without tiktoken | 1,530 passed, 5 skipped, 1,535 collected | 88.92% |
| With tiktoken 0.14.0 | 1,530 passed, 5 skipped, 1,535 collected | 88.90% |

Both retained the 80% floor. Four skips are Python 3.10-only TOML fallback tests;
one is the unavailable minisign executable. Pre-commit and the isolated automation
producer tests ran. Ruff, strict mypy, generated-reference freshness, dependency
consistency, self-host validation/manifest, tokenizer calibration and reference
conformance passed. The self-host checks establish no separate consumer adoption.
The preparation scripts also passed Ruff and strict mypy in the study worktree.
No packaging or publishing configuration changed; local release artifact checks
were not run. Remote verification, if run, is recorded separately from these logs.

Every command, exit, elapsed time and log digest is in
[preparation.json](preparation/preparation.json) or
[probe.json](public-probe/probe.json). Original stdout/stderr and JUnit reports
are retained. Paths in logs refer to disposable run directories. No private skill
contents, credentials, or upstream source files are redistributed here. Public
sources remain pinned at their upstream repository; its root license is CC BY-SA 4.0.

## Reproduction

From this study branch, with Linux CPython 3.12, Git, jq and network access to
GitHub/PyPI, run the following once with new output directory names:

```bash
python3 scripts/verify_workflow_study.py --output /tmp/tm-study-reproduce &&
python3 scripts/probe_public_workflow.py \
  --output /tmp/tm-public-reproduce \
  --python /tmp/tm-study-reproduce/heuristic-venv/bin/python
```

This was verified with fresh checkouts and environments. Both scripts pin source
revisions. TraceMantle's constraints pin resolved test dependencies; pip's venv
bootstrap version and host tools are recorded environmental assumptions, not
claims of byte-for-byte environment reproducibility. Test durations may differ.
The probe's own exit 0 means records were captured, not that each tool passed;
inspect its retained exit 1 validation and exit 4 manifest results. Neither script
runs a model or evaluates scored cases. An interrupted/failed setup retains its
completed command records and raises an error.

Offline, verify the retained log bytes without installing anything:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('docs/verification/workflow-study')
for report in [root/'preparation/preparation.json', root/'public-probe/probe.json']:
    data = json.loads(report.read_text())
    for name, expected in data['artifacts'].items():
        actual = hashlib.sha256((report.parent/'logs'/name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Changed artifact: {name}')
print('All retained log digests match')
PY
```

Offline digest verification does not rerun the checks. Re-execution needs package
downloads, Git source access and (for the optional tokenizer) its cold-cache data.
No model access or private consumer data is needed for either preparation script.

## Decision and smallest next step

There is no evidence here to justify adopting TraceMantle in the selected public
workflow or to claim net savings. The initial gate blocks a valid explanatory
example and incomplete coverage prevents legitimate skips. A real deployment,
consumer-specific frozen protocol, consecutive change history and full independent
reruns remain unfinished.

The smallest justified next step is to establish an actual downstream workflow
using this public skill, with its owner approving the required checks and input
scope, then resolve the example/reference distinction without weakening missing
resource detection. Alternatively, choose a currently used consumer whose skill
syntax is supported. Commit that scope and its live-run resource cap before any
scoring. Public-source access alone does not supply deployment or ground truth for
behavioral savings.
