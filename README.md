# TraceMantle

TraceMantle checks `SKILL.md` files for developers who write or maintain agent skills, finding invalid frontmatter, missing files, and portability problems before commit or CI. Optional evidence tracking helps you check whether earlier results still apply after a skill or its helpers change.

## Quick start

Requires Python 3.10 or later. Create an isolated environment and install the published release:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install tracemantle==1.7.0
tracemantle hello/SKILL.md
```

Use the path to your own skill in the last command. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. Need a first file? Copy the small [getting-started example](docs/getting-started.md#validate-your-first-skill).

Basic validation runs locally with no account, evaluator, signing key, or evidence policy. The default token estimate is offline.

## Read the result

The getting-started example produces:

```text
✔ PASS  hello/SKILL.md
            · info              description.quality-score  Description quality score: 95/100.

Checked 1 file: 1 passed, 0 failed
```

This file has no validation errors. The score is heuristic advice. For failures, fix the reported rule at the named file and line, then rerun. Passing file validation does not prove that a skill behaves correctly in a live agent.

Scan a directory with `tracemantle skills/`. Errors return a nonzero exit code; add `--strict` to fail on warnings too. Use `--format json` for structured results or `--help` for options.

## Optional evidence checks

Use evidence checks when a release needs approved results or you need to detect helper changes that invalidate earlier results. The [evidence workflow](docs/evidence-workflow.md) distinguishes manual approval from protected automation and neutral JSON imports.

## Task guides

- [Getting started](docs/getting-started.md): create and validate a skill.
- [CI setup](docs/ci.md): validate skills on pull requests.
- [Evidence workflow](docs/evidence-workflow.md): import results and approve their use.
- [CLI reference](docs/generated-reference.md): commands and configuration.
- [Troubleshooting](docs/getting-started.md#troubleshooting): understand diagnostics and exit codes.

[Contribute](CONTRIBUTING.md) · [Report an issue](https://github.com/moonrunnerkc/tracemantle/issues) · [Changelog](CHANGELOG.md) · [MIT license](LICENSE)
