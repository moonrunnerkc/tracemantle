<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/banner.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/banner.svg">
  <img alt="TraceMantle" src=".github/banner.svg" width="600">
</picture>

<br/>

<img src="https://img.shields.io/github/actions/workflow/status/moonrunnerkc/tracemantle/ci.yml?branch=main&style=flat-square" alt="CI status"> <img src="https://img.shields.io/github/license/moonrunnerkc/tracemantle?style=flat-square" alt="License">

</div>

TraceMantle validates agent skills, identifies changes to their packaged resources, and compares release evidence against a trusted policy. It analyzes files locally and imports evaluator output; it does not execute skills or run agents.

1168 tests cover all rule modules and the bundle/evidence workflow.

## Install

This checkout prepares version 1.6.0 locally. The TraceMantle distribution has not been published as part of this implementation.

```bash
git clone https://github.com/moonrunnerkc/tracemantle.git
cd tracemantle
python -m venv .venv
. .venv/bin/activate
python -m pip install .
tracemantle --version
python -m tracemantle --help
```

Requires Python 3.10 or later. The required runtime dependencies are PyYAML and, on Python 3.10 only, tomli. See [migration instructions](docs/migration.md) before replacing the old SkillCheck distribution. The default install creates no `skillcheck` executable.

## Usage

```bash
tracemantle skills/tracemantle/SKILL.md
tracemantle skills/ --analyze-graph --format json
tracemantle skills/tracemantle/SKILL.md --strict --ignore graph
```

Checks cover standard frontmatter, optional quality advice, line/token budgets, resource links, versioned compatibility advice, and heuristic capability graphs. `license`, `metadata`, and `compatibility` are standard fields. Keyword scores describe textual features; they do not establish trigger reliability or task success. Vendor runtime behavior without versioned evidence is marked unverified. See [profiles and conformance](docs/profiles.md) and the [generated CLI, configuration and rule reference](docs/generated-reference.md).

The shared document model uses one bounded source read and YAML parse per validation. Markdown resource parsing supports links, reference definitions, HTML links, directives and path-like inline code, with source spans; fenced examples and external schemes are distinguished. Reference depth means a chain through resources, not directory nesting. Limits and unsupported syntax are documented in [input and report contracts](docs/contracts.md).

## Compare bundles and evidence

```bash
tracemantle manifest skills/tracemantle --format json
tracemantle import-evidence evaluator-export.json --bundle path/to/skill --store evidence/ --format json
tracemantle compare baseline/skill candidate/skill \
  --trusted-root trusted-checkout --base-revision FULL_BASE_COMMIT_SHA \
  --evidence evidence/records/RECORD_SHA256.json --format json
```

The import example returns `unknown` until the export rows have complete identity bindings and trusted approval. The supported adapter is Promptfoo 0.118.10, results schema 3. The retained upstream fixture contains model judgments, so it cannot prove that an agent invoked a skill. Complete import bindings, policy fields, trust boundaries and runnable fixture examples are in [the evidence workflow](docs/evidence-workflow.md).

A bundle digest covers full file contents, normalized relative paths and executable bits. Changing a helper or schema changes the bundle even when SKILL.md stays the same. Missing or incompatible required evidence blocks release as `unknown`. Static reuse requires matching declared inputs; behavioral reuse also requires compatible execution conditions, freshness and an immutable model revision.

Comparison reads policy and checker bytes from a full trusted base commit SHA. Candidate-only policy or checker changes cannot weaken this gate. The tool never runs imported provider configuration, assertions, extensions, scripts or agent instructions.

## Configuration and token counting

Use `[tool.tracemantle]` in `pyproject.toml`, or `tracemantle.toml`. Legacy `skillcheck.toml` and `[tool.skillcheck]` are accepted with a stderr deprecation notice. Precedence is defaults, legacy fields, canonical fields, explicitly supplied CLI fields. Explicit default values such as `--format text` win. Settings are immutable and scoped to one project root; ambiguous mixed-root scans are rejected unless `--config` supplies a single explicit configuration.

```toml
[tool.tracemantle]
max-lines = 500
max-tokens = 8000
tokenizer = "heuristic"

[tool.tracemantle.frontmatter]
extension_fields = ["my-org-tag"]
reserved_words = ["acme", "internal"]
```

The default word/punctuation estimator is always offline. Installing an optional dependency never changes thresholds or selects a different backend. To explicitly select cl100k_base:

```bash
pip install '.[tiktoken]'
tracemantle skills/tracemantle/SKILL.md --tokenizer tiktoken --format json
```

Tiktoken may download its vocabulary on a cold cache. An unavailable backend produces a clear tool diagnostic; it never silently falls back. Both backends accept literal special-token markers as ordinary text. JSON reports identify the backend/version. Neither backend establishes another vendor's token count.

On the eight authored held-out texts in corpus v1, the unchanged heuristic has 37.4% median absolute relative error against cl100k_base. Across 24 budget decisions it produced zero false positives and one false negative. This small population is insufficient for broad calibration claims. [Measurements and corpus hashes](docs/verification/calibration-v1.json) separate token error, budget-decision error and semantic abstentions.

## Writes and history

Ordinary validation and comparison are read-only. Explicit `--history` writes immutable records under the skill directory's parent `.tracemantle/history/` directory, outside the bundle. Explicit import, migration and output destinations write only to the selected paths. Source artifacts and legacy ledgers are preserved. Concurrent history writers create separate records.

```bash
tracemantle skills/tracemantle/SKILL.md --history
tracemantle skills/tracemantle/SKILL.md --show-history --format json
tracemantle migrate-history path/to/skill/.skillcheck-history.json --store evidence/legacy
```

Legacy history does not contain sufficient identity for release evidence; migrating it records `unknown` comparability. No ordinary scan silently moves, migrates or deletes it.

## Exit codes and reports

Validation uses `0` for no errors, `1` for errors or strict warnings, `2` for input/tool errors, and `3` for semantic-only imported contradictions. Nonsemantic errors take priority over `3`. Filtering and final gate calculation happen after graph, imported and history diagnostics are merged. Each file's validity is separate from the overall gate.

Comparison uses `0` pass, `1` fail, `2` infrastructure-error, `4` unknown and `5` skipped. Required skipped checks become unknown and block release. Missing evidence does not assert that the skill itself failed. Text, versioned JSON and GitHub annotations derive from the same comparison result. Batch JSON is one parseable document.

## GitHub Action

The repository is [moonrunnerkc/tracemantle](https://github.com/moonrunnerkc/tracemantle). The old GitHub URL redirects here; existing tags still contain their original SkillCheck code. The composite [Action](action.yml) installs from its own checkout. Use `uses: ./` to test the unpublished source. [Trusted comparison workflow](.github/workflows/compare.yml) installs only the trusted tool and reads candidate files without execution.

After a separately authorized release creates `v1.6.0`, the Action reference will be:

```yaml
- uses: moonrunnerkc/tracemantle@v1.6.0
  with:
    path: skills/
```

For the unpublished candidate, replace the tag with a full CI-verified commit SHA. Do not use `@v1` to select TraceMantle until a TraceMantle release has updated that tag. Diagnostics appear as inline PR annotations; inputs are documented in [action.yml](action.yml).

## pre-commit

After the corresponding release tag exists, the pre-commit configuration is:

```yaml
repos:
  - repo: https://github.com/moonrunnerkc/tracemantle
    rev: v1.6.0
    hooks:
      - id: tracemantle
```

## Releases

`make verify-release` runs lint, strict typing, the full coverage gate, self-host checks, packaging and clean installed-artifact verification. Release candidates reuse the complete CI workflow; publishing consumes its exact verified artifacts and retains attestations/trusted publishing. The Release workflow is disabled in GitHub, and `TRACEMANTLE_PUBLISH_ENABLED=false`. Enabling it, creating release tags and publishing require a separate explicit instruction after the new PyPI publisher is verified. See [the owner rename checklist](docs/rename-checklist.md).

After an authorized release, verify each downloaded artifact against this repository and the full immutable release commit:

```bash
gh attestation verify dist/tracemantle-1.6.0-py3-none-any.whl \
  --repo moonrunnerkc/tracemantle --source-digest FULL_RELEASE_COMMIT_SHA
```

Ordinary CI artifacts are not attested or published. PyPI badges will be restored only after the new distribution exists.

## Documentation

- [Implementation ledger](docs/implementation-status.md) and [rename checklist](docs/rename-checklist.md).
- [Migration](docs/migration.md) and [contributor instructions](CONTRIBUTING.md).
- [Historical corpus runs](docs/case-study-v1-real-world-runs.md) and [dirname-mismatch case study](docs/case-study-silent-skill-failure.md).
- [Installed skill](skills/tracemantle/SKILL.md).

## License

MIT. See [LICENSE](LICENSE).
