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

Configuration precedence remains defaults, legacy config, canonical pyproject
config, canonical standalone config, then explicit CLI flags. See
[migration](migration.md) for existing installations and the
[generated reference](generated-reference.md) for supported keys. The
[pre-commit example](migration.md#repository-and-integrations) is another option.

Evidence comparison requires a separate trusted-tooling workflow. Follow the
[manual route](evidence-workflow.md#trusted-policy) or the
[protected automation route](evidence-workflow.md#protected-automation).
Do not execute candidate-provided adapters or workflow files with approval keys.
