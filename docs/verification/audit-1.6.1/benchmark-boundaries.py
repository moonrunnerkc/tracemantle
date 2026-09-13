"""Supplemental deterministic dependency-parser workloads; no skills execute."""
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
    'escaped-and-list-links': '\n'.join(
        f'\\` [real](helper-{i}.py) `\n\n- Steps:\n    - [nested](nested-{i}.py)\n\n'
        f'- Examples:\n\n      [example](missing-{i}.py)\n\n'
        for i in range(1000)
    ),
    'long-backslash-runs': ('\\' * 10001 + '` [real](helper.py) `\n\n') * 100,
    'unmatched-delimiter-lengths': '\n\n'.join('Text ' + '`' * i + ' [real](helper.py)' for i in range(1, 1400)),
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
