# Contributing

## Testing

Run the suite from the repo root after installing the dev extras:

```bash
pip install -e ".[dev]"
make test          # full suite, enforces the coverage floor
pytest tests/ -v   # same suite, reports coverage but does not gate on it
```

Coverage is measured on every run but the floor is only applied by `make test`, `make verify-release`, and CI. That keeps single-file runs (`pytest tests/test_sizing.py`) usable: whole-package coverage on one test file is near zero, and a floor in `addopts` failed those runs unconditionally.

The README test-count line (`N tests cover ...`) is asserted by `tests/test_readme_test_count_claim.py`; when you add or remove tests, bump the README count in the same commit.

### Platform-skipped tests

A handful of tests skip on Windows because the underlying OS feature is unavailable or behaves differently. `pytest --collect-only` still counts them, so the README's `N tests cover ...` number is the same on every platform; only the pass/skip ratio shifts.

- `tests/test_cli.py`: directory-symlink discovery skips on Windows because symlink creation requires privileges.
- `tests/test_references.py`: the two `os.symlink`-based tests use the module-level `_skip_symlink = pytest.mark.skipif(sys.platform == "win32", ...)` mark. `os.symlink` on Windows requires developer mode or admin privileges, so the symlink-escape coverage runs on Linux/macOS only.
- `tests/test_cli_history.py` and `tests/test_history_io.py`: each has one `pytest.mark.skipif(sys.platform == "win32", ...)` test exercising POSIX file-mode permission errors that Windows does not enforce identically.
- `tests/test_config_validation.py`: four TOML fallback tests run on Python 3.10 and skip on newer interpreters, which use `tomllib`.
- `tests/test_pre_commit.py`: both tests skip wherever the `pre-commit` binary is not installed. CI installs `pre-commit` so they run there; local runs without `pre-commit` show them as skipped.

## Release candidates

Install the constrained development/build tools and run the complete local gate:

```bash
pip install -c constraints-dev.txt -e '.[dev]'
make verify-release
```

The release workflow reuses the entire CI workflow, including the supported OS/Python matrix, strict typing, lint, the unchanged 80% coverage floor, optional-tokenizer checks and clean wheel/source installs. It downloads those exact tested artifacts, checks the distribution identity, retains provenance attestations and uses PyPI trusted publishing. A failed quality job cannot reach publishing. Candidate artifacts are built with `--no-isolation` after installing constrained build tools, so build versions are reproducible without pinning consumer runtime requirements.

The Release workflow is disabled in GitHub and `TRACEMANTLE_PUBLISH_ENABLED=false`. A separate explicit publishing instruction is required before enabling either safeguard, after configuring the new distribution's trusted publisher. See [rename-checklist.md](docs/rename-checklist.md). Do not upload a TraceMantle artifact to the legacy SkillCheck project. Local checks do not establish remote CI success or a public release.

Keep the package, self-host skill and changelog versions coherent. `python scripts/generate_reference.py --check` verifies generated CLI/config/rule documentation. New behavior needs real fixtures and independent assertions; retained upstream fixtures must keep their license and provenance intact. The [implementation ledger](docs/implementation-status.md) records requirement acceptance and remaining external prerequisites.
