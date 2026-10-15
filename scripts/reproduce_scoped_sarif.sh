#!/usr/bin/env bash
set -euo pipefail
# Reproduce the pinned deterministic study in a new checkout and environment.
if [ "$#" -ne 1 ]; then
  echo 'Usage: bash scripts/reproduce_scoped_sarif.sh /absolute/new-output-directory' >&2
  exit 2
fi
study_output=$1
if [ -e "$study_output" ]; then
  echo 'Output directory must not already exist.' >&2
  exit 2
fi
study_source=$(git rev-parse --show-toplevel)
mkdir -p "$study_output"
study_output=$(cd "$study_output" && pwd)
git clone --no-hardlinks "$study_source" "$study_output/repo"
git -C "$study_output/repo" checkout --detach fe92958c5d7748933560bc4a8f6fe6c4daa9e4cf
python3.12 -m venv "$study_output/venv"
source "$study_output/venv/bin/activate"
cd "$study_output/repo"
python -m pip install -c constraints-dev.txt -e '.[dev]' > "$study_output/install.log" 2>&1
command -v jq
python scripts/evaluate_scoped_sarif.py seed --output "$study_output/seed" > "$study_output/seed.log" 2>&1
python scripts/evaluate_scoped_sarif.py evaluate --seed "$study_output/seed" --output "$study_output/results" > "$study_output/evaluate.log" 2>&1
python - "$study_output/results/results.json" <<'PY'
import json, sys
from pathlib import Path
results = json.loads(Path(sys.argv[1]).read_text())
assert len(results['rows']) == 48
assert all(not row['verification']['failures'] for row in results['rows'])
for arm in ('B', 'C'):
    assert sum(row['verification']['justified_skips'][arm] for row in results['rows']) == 51
print('48 trials, 51 independently checked skips per mechanism; all required outcomes agree.')
print('Full experiment seconds:', results['seconds'])
PY
