#!/usr/bin/env bash
set -euo pipefail
# Fresh dependencies and source; network is needed only for dependency installation.
source_repo=$(git rev-parse --show-toplevel)
study_output=${1:?Usage: bash scripts/reproduce_sarif_study.sh NEW_EXTERNAL_DIRECTORY}
mkdir "$study_output"
study_output=$(realpath "$study_output")
git clone --quiet --no-hardlinks "$source_repo" "$study_output/repo"
git -C "$study_output/repo" checkout --quiet --detach 42bba507fe5ff13fb8bd10a3d3ed7261b8be20f3
python3.12 -m venv "$study_output/venv"
"$study_output/venv/bin/python" -m pip install --no-cache-dir -c "$study_output/repo/constraints-dev.txt" -e "$study_output/repo[dev]" > "$study_output/install.log" 2>&1
export PATH="$study_output/venv/bin:$PATH"
cd "$study_output/repo"
python scripts/evaluate_sarif_workflow.py seed --output "$study_output/seed"
python scripts/evaluate_sarif_workflow.py evaluate --seed "$study_output/seed" --output "$study_output/results"
python - "$study_output/results/results.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))['rows']
assert len(rows) == 66
for row in rows:
    for arm in ('A', 'B', 'C'):
        assert not any(c['reused'] for c in row['arms'][arm]['checks'])
    before = [c['errors'] for c in row['arms']['B']['checks']]
    assert all([c['errors'] for c in row['arms'][a]['checks']] == before for a in ('A', 'C'))
print('Reproduced 66 trials; all arms agree, no reused checks. Inspect per-case outputs and timings.')
PY
