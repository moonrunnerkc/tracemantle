# Validate skills in CI

Ordinary validation needs no evidence policy or evaluator. Add this workflow to
`.github/workflows/skills.yml` in the repository containing your skills:

```yaml
name: Validate skills
on: [push, pull_request]
permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
      - uses: moonrunnerkc/tracemantle@v1.7.0
        with:
          path: skills/
          strict: 'true'
```

This uses published 1.7.0. Review the [Action inputs](../action.yml) to select
report format or change thresholds. Pin the Action's full release commit if
required by your repository policy. Remove `strict` to allow warnings while
still rejecting errors. Directory discovery is recursive and does not follow
directory symlinks.

For any CI system, install Python 3.10+ and run:

```bash
python -m pip install tracemantle==1.7.0
tracemantle skills/ --strict --format json
```

## Changed skills only (unreleased)

In a large skills repository, `--changed-since REV` validates only skills with
a committed, staged, unstaged or untracked change anywhere under their
directory since `REV`, helpers included. It exits 0 when nothing changed. Fetch
enough history for the revision to resolve:

```bash
git fetch --no-tags origin main
tracemantle skills/ --changed-since origin/main --strict
```

It requires a release after 1.7.0 and cannot be combined with
`--show-history` or the ingest flags, which name a single skill.

## Code scanning (unreleased)

`--format sarif` writes a SARIF 2.1.0 log, so diagnostics appear as GitHub
code-scanning alerts that persist across pull requests. It requires a release
after 1.7.0. The validation step still fails on errors; the upload runs anyway:

```yaml
permissions:
  contents: read
  security-events: write
steps:
  - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
  - run: python -m pip install tracemantle
  - run: tracemantle skills/ --format sarif > tracemantle.sarif
  - uses: github/codeql-action/upload-sarif@v3  # pin a full commit SHA if your policy requires it
    if: always()
    with:
      sarif_file: tracemantle.sarif
```

Errors map to `error`, warnings to `warning` and informational advice to
`note`. The log records the gate's exit code in its invocation.

Configuration precedence remains defaults, legacy config, canonical pyproject
config, canonical standalone config, then explicit CLI flags. See
[migration](migration.md) for existing installations and the
[generated reference](generated-reference.md) for supported keys. The
[pre-commit example](migration.md#repository-and-integrations) is another option.

Evidence comparison requires a separate trusted-tooling workflow. Follow the
[manual route](evidence-workflow.md#trusted-policy) or the
[protected automation route](evidence-workflow.md#protected-automation).
Do not execute candidate-provided adapters or workflow files with approval keys.
