.PHONY: lint test regen-golden regen-golden-warnings regen-self-host-fixtures verify-release

# Coverage floor for full-suite runs. Not in pyproject addopts, which would also
# apply it to single-file runs; see the comment there.
COV_FLOOR := 80

# Pre-1.0 sentinel version. Stale references to this string must not appear in
# shipped files; update only if a new major version creates a new legacy line.
LEGACY_VERSION := 0.2.0

# Current package version, read from pyproject.toml. Used to assert the README's
# pre-commit `rev:` example tracks the shipped version.
VERSION := $(shell grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')

regen-self-host-fixtures:
	python3 scripts/regen_self_host_fixtures.py

# Rewrite tests/fixtures/golden/ from the current renderers. Read the diff
# before committing: a golden that moves without a formatters.py change means
# something upstream shifted.
regen-golden:
	TRACEMANTLE_REGEN_GOLDEN=1 python3 -m pytest tests/test_formatter_golden.py -q

# Rewrite tests/golden/*/expected.txt from the current rules. Same rule as
# above: read the diff, a golden that moves on its own is a regression.
regen-golden-warnings:
	TRACEMANTLE_REGEN_GOLDEN=1 python3 -m pytest tests/test_golden_warnings.py -q

lint:
	ruff check src tests scripts
	mypy

test:
	python3 -m pytest tests/ --cov-fail-under=$(COV_FLOOR)

verify-release:
	ruff check src tests scripts
	mypy
	python3 -m pytest tests/ -v --cov-fail-under=$(COV_FLOOR)
	tracemantle --version
	tracemantle skills/tracemantle/SKILL.md
	tracemantle skills/tracemantle/SKILL.md --analyze-graph
	@if grep -rn "$(LEGACY_VERSION)" --include="*.py" --include="*.toml" --include="*.md" --include="*.yml" src/ pyproject.toml README.md action.yml ; then echo "FAIL: $(LEGACY_VERSION) references found"; exit 1; fi
	@if grep -En "moonrunnerkc/(skillcheck|tracemantle)@v0" README.md; then echo "FAIL: @v0 reference in README"; exit 1; fi
	@grep -q "rev: v$(VERSION)" README.md && echo "OK: README pre-commit rev matches v$(VERSION)" || { echo "FAIL: README pre-commit 'rev:' does not match pyproject version v$(VERSION); update the rev in README.md"; exit 1; }
	python3 -m build --no-isolation --outdir candidate-dist
	python3 scripts/verify_artifacts.py candidate-dist
