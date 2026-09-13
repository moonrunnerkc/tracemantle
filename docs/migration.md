# Migrating SkillCheck to TraceMantle

TraceMantle is a different distribution. Installing it is not an automatic upgrade of `skillcheck`. Before uninstalling anything, verify that the installed `skillcheck` distribution is this project's old analyzer, not an unrelated package or executable with the same name. Prefer a clean virtual environment.

The supported replacement sequence, verified with locally built old and new artifacts, is:

```bash
python -m pip show skillcheck
# Only after identifying this project's old distribution:
python -m pip uninstall skillcheck
python -m pip install tracemantle==1.6.0
tracemantle --version
python -m tracemantle --version
```

Do not install the old and new distributions together: compatibility wrappers occupy the old Python package's paths. The new distribution installs only the `tracemantle` console script. If a private shell workflow needs the old command temporarily, an explicit shell alias `alias skillcheck=tracemantle` is an opt-in option; do not replace another product's command.

The documented top-level imports (`validate`, `Diagnostic`, `Severity`, `ValidationResult`, `ParsedSkill`, `ParseError`, `__version__`) and the core/agents imports have thin deprecated wrappers. Prefer `from tracemantle import validate`. Importing `skillcheck` emits a `DeprecationWarning`. Old internal configuration mutators were removed; pass immutable `DocumentSettings` to `parse()` or `validate()` instead. There is no legacy console-script installation or `python -m skillcheck` entry point.

Configuration is merged per field at the selected project root: defaults, `skillcheck.toml` and `[tool.skillcheck]`, `[tool.tracemantle]`, `tracemantle.toml`, then explicit CLI arguments. Canonical standalone fields take precedence over canonical pyproject fields. Legacy use warns on stderr, preserving machine stdout. Rename the standalone file or move its fields under `[tool.tracemantle]`; frontmatter options go under `[tool.tracemantle.frontmatter]`. An explicit `--config` selects one file for the invocation. Projects with different discovered config roots require separate invocations.

The fixes under `[Unreleased]` retain this installation and migration sequence; released examples continue to pin 1.6.0. Source verification builds still carry the baseline package version until release preparation and must be identified by their source revision and artifact digest. They are not replacements for published artifacts. The dependency-discovery and numeric-overflow fixes also remain unreleased. They do not change the migration sequence or the supported Promptfoo adapter version. Automatic discovery now reports malformed `tool` tables as input errors; `--format json` preserves a machine-readable error envelope.

Test regeneration environment settings are now `TRACEMANTLE_REGEN_GOLDEN`. No runtime environment-based configuration was added. Third-party tokenizer cache settings retain their own names.

Legacy `.skillcheck-history.json` files remain readable. To migrate, select a destination outside the evaluated skill directory:

```bash
tracemantle migrate-history skill/.skillcheck-history.json --store evidence/legacy --format json
```

Migration validates the complete ledger, preserves its original bytes in `sources/`, and writes content-addressed records in `records/`. It never changes or removes the source. Repetition produces the same destinations and does not duplicate records. Existing content with a matching digest must be identical; conflicting content is refused. There is no implicit overwrite option. Legacy records remain incomparable for release gating because they lack bundle/configuration/checker/fixture/execution identity.

New `--history` writes one immutable record per run outside the bundle. Its name is a full SHA-256 of its record, including a unique run ID, so concurrent writers cannot replace each other's records. History record schema 2 retains the v1 entry field `skillcheck_version`; it is a historical data identifier, not the current distribution name. Legacy `save_ledger`/`append_run` imports remain compatibility APIs for explicitly requested v1 writes, with their historical single-writer limitation; the CLI uses the immutable store.

Validation JSON is now envelope schema 2. Existing file summaries and diagnostics remain, with explicit tool identity, tokenizer provenance and an overall gate. Heuristic graph locations use full-file coordinates. Graph-v1 imports still express body-relative locations; the wrapper converts them to full-file locations without reinterpreting the stored v1 input schema. Critique-v1 and graph-v1 `$id` values remain stable, with compatibility copies at their old source paths.

## Repository and integrations

The repository is now [moonrunnerkc/tracemantle](https://github.com/moonrunnerkc/tracemantle). GitHub redirects the old URL, but update active clone URLs, pre-commit repositories and Action references. Preserve your remote's existing transport:

```bash
# For an existing HTTPS remote:
git remote set-url origin https://github.com/moonrunnerkc/tracemantle.git
# For an existing SSH remote:
git remote set-url origin git@github.com:moonrunnerkc/tracemantle.git
```

If you also rename the local checkout directory, recreate its virtual environment: installed console scripts can retain absolute paths to the old directory.

The installed skill now lives at `skills/tracemantle/SKILL.md`. Version tags before 1.6.0 still identify SkillCheck source. Use `moonrunnerkc/tracemantle@v1.6.0` for TraceMantle, or pin a full CI-verified commit SHA. Renaming the repository does not publish the distribution or update downstream repositories automatically.

For pre-commit, pin the TraceMantle release:

```yaml
repos:
  - repo: https://github.com/moonrunnerkc/tracemantle
    rev: v1.6.0
    hooks:
      - id: tracemantle
```
