"""Setext and adjacent block workloads; no skills execute."""
from __future__ import annotations

import hashlib
import json
import platform
import statistics
import time
import tracemalloc
from pathlib import Path

import tracemantle.markdown as markdown

CASES = {
    'setext-links-1000': '\n\n'.join(
        f'`Title {i}\n======\n[helper](helper-{i}.py) `' for i in range(1000)
    ),
    'multiline-heading-spans-1000': '\n\n'.join(
        f'- `Example\n  [example](missing-{i}.py) `\n  --\n  [helper](helper-{i}.py)' for i in range(1000)
    ),
    'long-underlines': '`Title\n' + '=' * 500000 + '\n[helper](helper.py) `',
    'near-thematic-breaks': ('Text\n' + '* ' * 10000 + 'x\n\n') * 10,
}

report = {
    'python': platform.python_version(),
    'platform': platform.platform(),
    'implementation_sha256': hashlib.sha256(Path(markdown.__file__).read_bytes()).hexdigest(),
    'repeats': 5,
    'workloads': {},
}
for name, body in CASES.items():
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        result = markdown.tokenize(body)
        samples.append(time.perf_counter() - start)
    tracemalloc.start()
    result = markdown.tokenize(body)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    report['workloads'][name] = {
        'corpus_bytes': len(body.encode()),
        'corpus_sha256': hashlib.sha256(body.encode()).hexdigest(),
        'seconds': samples,
        'median': statistics.median(samples),
        'spread': max(samples) - min(samples),
        'peak_python_bytes': peak,
        'resource_count': len(result.resources),
        'uncertain': result.uncertain,
    }
print(json.dumps(report, indent=2))
