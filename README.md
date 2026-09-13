<!-- Layout adapted from https://github.com/othneildrew/Best-README-Template. -->
<a id="readme-top"></a>

<div align="center">
  <img src=".github/banner.svg" alt="TraceMantle" width="600">
  <p>Validate agent skills and check the evidence behind a release.</p>
  <p>
    <a href="docs/generated-reference.md"><strong>CLI reference</strong></a>
    &middot;
    <a href="https://github.com/moonrunnerkc/tracemantle/issues/new">Report a bug or request a feature</a>
  </p>
  <a href="https://github.com/moonrunnerkc/tracemantle/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/moonrunnerkc/tracemantle/ci.yml?branch=main&amp;style=flat-square" alt="CI status"></a>
  <a href="https://pypi.org/project/tracemantle/"><img src="https://img.shields.io/pypi/v/tracemantle?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/tracemantle/"><img src="https://img.shields.io/pypi/pyversions/tracemantle?style=flat-square" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/moonrunnerkc/tracemantle?style=flat-square" alt="MIT license"></a>
</div>

<details>
  <summary>Contents</summary>
  <ol>
    <li><a href="#about-the-project">About the project</a></li>
    <li><a href="#getting-started">Getting started</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#integrations">Integrations</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license-and-contact">License and contact</a></li>
  </ol>
</details>

## About the project

TraceMantle is a Python CLI and library for checking agent skill bundles before they are committed or released. It provides:

- **Skill validation:** checks `SKILL.md` frontmatter, file references, size limits and compatibility advice against the [Agent Skills specification](https://agentskills.io/specification).
- **Bundle tracking:** hashes skill files and packaged resources so helper changes are detected too.
- **Evidence checks:** imports evaluator results and compares bundles against trusted policies. Missing, stale or incompatible evidence blocks the gate.

TraceMantle analyzes files; it does not execute skills or evaluators. Static checks and imported model judgments do not prove that a skill works in a live agent.

## Getting started

Requires Python 3.10 or later. Install in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install tracemantle==1.6.0
tracemantle --version
```

Installation examples use released 1.6.0. Subsequent fixes are listed under [Unreleased](CHANGELOG.md#unreleased); source verification is recorded in the [implementation ledger](docs/implementation-status.md).

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. Replacing SkillCheck? Follow the [migration guide](docs/migration.md) before installing.

## Usage

Validate a skill, scan a directory, or inspect a bundle:

```bash
tracemantle path/to/SKILL.md
tracemantle path/to/skills/ --strict --format json
tracemantle path/to/SKILL.md --analyze-graph
tracemantle manifest path/to/skill --format json
```

Validation exits `0` when it passes and nonzero on errors; `--strict` also fails on warnings. Text, JSON and GitHub annotation output are supported.

For release evidence, use `import-evidence` and `compare` with a trusted base revision and approved evidence. The [evidence workflow](docs/evidence-workflow.md) covers setup, supported imports and runnable examples.

Configure defaults in `tracemantle.toml` or `[tool.tracemantle]` in `pyproject.toml`. Explicit CLI flags take precedence. Token counting uses an offline estimate by default; optional `tiktoken` counting must be selected explicitly.

See the [CLI and configuration reference](docs/generated-reference.md), [compatibility profiles](docs/profiles.md) and [input limits](docs/contracts.md) for details.

## Integrations

Use the composite GitHub Action pinned to a release:

```yaml
- uses: moonrunnerkc/tracemantle@v1.6.0
  with:
    path: skills/
```

[Action inputs](action.yml) control validation and reporting. Versions before 1.6.0 contain the older SkillCheck implementation. A [pre-commit hook](.pre-commit-hooks.yaml), [Python API](src/tracemantle/__init__.py) and [installed skill](skills/tracemantle/SKILL.md) are also included.

## Contributing

1350 tests cover validation, CLI integrations, bundle identity and evidence checks. CI runs Python 3.10 through 3.13 on Linux, macOS and Windows, plus optional-tokenizer and clean package-install checks.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and verification. Submit fixes through pull requests; use [issues](https://github.com/moonrunnerkc/tracemantle/issues) for bugs and proposals. Changes are recorded in the [changelog](CHANGELOG.md).

## License and contact

[MIT](LICENSE). Maintained by [moonrunnerkc](https://github.com/moonrunnerkc), Aftermath Technologies Ltd.
