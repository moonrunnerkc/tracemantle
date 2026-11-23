# Contributing

Use `moonrunnerkc` as the Git author name for the repository owner's work. Other contributors retain their own attribution.

## Testing

Run the suite from the repo root after installing the dev extras:

```bash
pip install -e ".[dev]"
make test          # full suite, enforces the coverage floor
pytest tests/ -v   # same suite, reports coverage but does not gate on it
```

Coverage is measured on every run but the floor is only applied by `make test`, `make verify-release`, and CI. That keeps single-file runs (`pytest tests/test_sizing.py`) usable: whole-package coverage on one test file is near zero, and a floor in `addopts` failed those runs unconditionally.

The implementation ledger test-count line (`N tests cover ...`) is asserted by `tests/test_readme_test_count_claim.py`; when you add or remove tests, bump the count in `docs/implementation-status.md` in the same commit.

### Platform-skipped tests

A handful of tests skip on Windows because the underlying OS feature is unavailable or behaves differently. `pytest --collect-only` still counts them, so the ledger's `N tests cover ...` number is the same on every platform; only the pass/skip ratio shifts.

- `tests/test_cli.py`: directory-symlink discovery skips on Windows because symlink creation requires privileges.
- `tests/test_references.py`: the two `os.symlink`-based tests use the module-level `_skip_symlink = pytest.mark.skipif(sys.platform == "win32", ...)` mark. `os.symlink` on Windows requires developer mode or admin privileges, so the symlink-escape coverage runs on Linux/macOS only.
- `tests/test_cli_history.py` and `tests/test_history_io.py`: each has one `pytest.mark.skipif(sys.platform == "win32", ...)` test exercising POSIX file-mode permission errors that Windows does not enforce identically.
- `tests/test_config_validation.py`: four TOML fallback tests run on Python 3.10 and skip on newer interpreters, which use `tomllib`.
- `tests/test_changed_since.py`: the whole module skips where `git` is not installed.
- `tests/test_pre_commit.py`: both tests skip wherever the `pre-commit` binary is not installed. CI installs `pre-commit` so they run there; local runs without `pre-commit` show them as skipped.

## Supported interpreters and dependencies

CI runs the suite on Python 3.10 through 3.15 on Linux, macOS and Windows. Python 3.10 is past upstream end of life and is kept as legacy compatibility; see [Python support](docs/migration.md#python-support) before changing the minimum. `constraints-dev.txt` pins the development, build and audit tools, with interpreter markers where one version cannot cover the whole range. `uv.lock` is the lock for `uv` users and is refreshed with `uv lock`; CI installs from the constraints file.

The `audit` job resolves the runtime and tokenizer dependencies on 3.10 and 3.15 and checks them against published advisories. It needs network access and never runs during ordinary validation. To run it yourself:

```bash
python -m venv /tmp/runtime && /tmp/runtime/bin/python -m pip install -c constraints-dev.txt '.[tiktoken]'
/tmp/runtime/bin/python -m pip freeze --exclude tracemantle > /tmp/runtime-requirements.txt
python -m pip install -c constraints-dev.txt pip-audit
python scripts/audit_dependencies.py /tmp/runtime-requirements.txt
```

Exit 1 means an advisory applies; move the pin to a fixed release. Exit 2 means the audit did not complete, for example because the advisory service was unreachable, and is not a clean result. Do not add an advisory exception without an analysis showing the affected code path is not used, scoped to that one advisory.

[Dependabot](.github/dependabot.yml) proposes weekly updates for GitHub Actions and Python dependencies. Nothing merges automatically. It has not yet been observed updating the marker-qualified lines in `constraints-dev.txt`; check those by hand.

The `CI gate` job is the check a branch rule should require. It always runs and fails unless every other CI job succeeded, so a skipped or cancelled job cannot pass for it. Add a new job to its `needs` list and its expected set.

## Release candidates

Install the constrained development/build tools and run the complete local gate:

```bash
pip install -c constraints-dev.txt -e '.[dev]'
make verify-release
```

The release workflow reuses the entire CI workflow, including the supported OS/Python matrix, strict typing, lint, the unchanged 80% coverage floor, optional-tokenizer checks and clean wheel/source installs. It downloads those exact tested artifacts, checks the distribution identity, retains provenance attestations and uses PyPI trusted publishing. The quality-gated approvals job installs OpenSSH, minisign and bubblewrap, rejects skipped signature/producer tests, and exercises the Action from the same source. A failed quality job cannot reach publishing. Candidate artifacts are built with `--no-isolation` after installing constrained build tools, so build versions are reproducible without pinning consumer runtime requirements.

Publishing requires an explicit owner instruction. The Release workflow and `TRACEMANTLE_PUBLISH_ENABLED` are normally disabled; enable them for an authorized release, then disable them again after it completes. The `pypi` environment accepts version-tag refs only, and PyPI must trust `moonrunnerkc / tracemantle / release.yml / pypi`. See [rename-checklist.md](docs/rename-checklist.md). Do not upload a TraceMantle artifact to the legacy SkillCheck project. Local checks do not establish remote CI success or a public release. The manual `verify-gates.yml` workflow exercises a failed prerequisite with a nonpublishing sentinel; its expected quality failure and skipped sentinel must be checked individually. It never enables Release.

Keep the package, self-host skill and changelog versions coherent. `python scripts/generate_reference.py --check` verifies generated CLI/config/rule documentation. New behavior needs real fixtures and independent assertions; retained upstream fixtures must keep their license and provenance intact. The [implementation ledger](docs/implementation-status.md) records requirement acceptance and remaining external prerequisites.
