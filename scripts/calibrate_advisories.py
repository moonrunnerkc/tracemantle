"""Measure token error separately from budget-decision error on held-out texts."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from tracemantle.tokenizer import estimate_tokens, tokenizer_provenance

ROOT = Path(__file__).resolve().parents[1]


def measure() -> dict[str, object]:
    files = sorted((ROOT / 'tests/fixtures/tracemantle/held-out').glob('*.txt'))
    rows = []
    errors: list[float] = []
    decisions = {'true_positive': 0, 'true_negative': 0, 'false_positive': 0, 'false_negative': 0, 'abstentions': 0}
    for path in files:
        text = path.read_text()
        estimated = estimate_tokens(text, 'heuristic')
        reference = estimate_tokens(text, 'tiktoken')
        # The reference labels budget crossing only, not skill quality or success.
        for budget in (100, 1000, 5000):
            actual, predicted = reference > budget, estimated > budget
            label = ('true_positive' if actual else 'false_positive') if predicted else ('false_negative' if actual else 'true_negative')
            decisions[label] += 1
        errors.append(abs((estimated - reference) / reference))
        rows.append({'case': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'heuristic': estimated, 'cl100k_base': reference, 'relative_error': (estimated - reference) / reference})
    return {'corpus': 'tracemantle-held-out-v1', 'license': 'MIT', 'population': '8 authored held-out texts; four prose languages, two code forms, small and large inputs',
            'tokenizer': tokenizer_provenance('tiktoken'), 'heuristic_before': 'word-punctuation-v1', 'heuristic_after': 'word-punctuation-v1 (unchanged)',
            'median_absolute_relative_error': statistics.median(errors),
            'budget_decisions': decisions, 'keyword_quality': {'abstentions': len(rows), 'reason': 'No independent semantic quality labels; calibration is insufficient.'},
            'scope': 'Token error against cl100k_base is not trigger reliability or task success.', 'cases': rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(measure(), indent=2, ensure_ascii=True) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
