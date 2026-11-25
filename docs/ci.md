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
      - uses: moonrunnerkc/tracemantle@v1.9.0
        with:
          path: skills/
          strict: 'true'
```

This uses published 1.9.0. Review the [Action inputs](../action.yml) to select
report format or change thresholds. Pin the Action's full release commit if
required by your repository policy. Remove `strict` to allow warnings while
still rejecting errors. Directory discovery is recursive and does not follow
directory symlinks.

For any CI system, install a supported Python (3.11 or later is recommended; see
[migration](migration.md#python-support)) and run:

```bash
python -m pip install tracemantle==1.9.0
tracemantle skills/ --strict --format json
```

## Changed skills only

In a large skills repository, `--changed-since REV` validates only skills with
a committed, staged, unstaged or untracked change anywhere under their
directory since `REV`, helpers included (since 1.8.0). It exits 0 when nothing changed. Fetch
enough history for the revision to resolve:

```bash
git fetch --no-tags origin main
tracemantle skills/ --changed-since origin/main --strict
```

It cannot be combined with `--show-history` or the ingest flags, which name a
single skill.

A change to configuration that applies to a skill also selects it: an edited,
created, deleted or renamed `tracemantle.toml`, `skillcheck.toml` or
`pyproject.toml` tool table in the skill's directory or above it, up to the
repository root. With `--config FILE`, a changed file selects every skill.
Configuration with no committed baseline at `REV`, such as a git-ignored
`tracemantle.toml` or a `--config` file outside the repository, cannot be
shown unchanged, so the skills it applies to are validated and stderr says why.

Configuration reached through a symbolic link is compared only in the simple
case: the link and its target are both committed in the repository, the link
points directly at the file through no other link, and neither changed since
`REV`. A link to a file outside the repository, a chain of links, a link
through a linked directory, link text with a `name/..` step, and a broken or
cyclic link cannot be shown unchanged, so every run validates the skills that configuration applies to
(since 1.9.0). Commit a regular file, or link directly to a committed one, to
keep the run selective.

The selection reflects file changes only. A skill that was not selected has
not been shown to pass under a different TraceMantle version, Python
environment or command-line flags. Run a full scan after changing any of those.

## Contributions you have not reviewed

A skill can suppress its own diagnostics with a frontmatter comment, and a
repository can relax limits in its configuration. When validating a pull
request from a fork, refuse the comments and take configuration from the base
branch:

```bash
tracemantle skills/ --strict --no-inline-ignores --config "$TRUSTED_CHECKOUT/tracemantle.toml"
```

The Action input is `no-inline-ignores: 'true'`. Refused comments are reported
as `ignore.inline-refused` (since 1.9.0).

## Machine-readable failures

With `--format json`, an input failure such as a missing path or an unusable
revision prints one JSON object with `gate.exit_code` 2 and an `errors` array,
and exits 2. Parse stdout before checking for results. Arguments the parser
cannot read still produce a usage message on stderr. See
[contracts](contracts.md).

## Code scanning

`--format sarif` writes a SARIF 2.1.0 log, so diagnostics appear as GitHub
code-scanning alerts that persist across pull requests (since 1.8.0). The
validation step still fails on errors; the upload runs anyway:

```yaml
permissions:
  contents: read
  security-events: write
steps:
  - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
  - run: python -m pip install tracemantle==1.9.0
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
