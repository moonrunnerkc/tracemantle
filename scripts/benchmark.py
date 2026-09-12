"""Repeated cold CLI, warm batch, graph/report and bounded stress measurements."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any

TEXT = '---\nname: sample\ndescription: Validates Python modules when users request source checks and reports errors.\n---\n# Validate modules\nRead the Python source and return findings.\n'


def measure(action: Callable[[], object], repeats: int) -> dict[str, object]:
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        action()
        timings.append(time.perf_counter() - start)
    return {'seconds': timings, 'median': statistics.median(timings), 'spread': max(timings) - min(timings)}


def benchmark(package: str, repeats: int) -> dict[str, Any]:
    api = importlib.import_module(package)
    parser = importlib.import_module(package + '.parser')
    graph = importlib.import_module(package + '.core.graph')
    formatter = importlib.import_module(package + '.formatters')
    tokenizer: Any = importlib.import_module(package + '.tokenizer')
    assert api.__file__ is not None
    package_root = Path(api.__file__).parent
    modern = package == 'tracemantle'
    if not modern:
        tokenizer._tiktoken_available = True
        tokenizer._tiktoken_enc = None
    results: dict[str, Any] = {'python': sys.version, 'platform': platform.platform(), 'package': package, 'version': api.__version__,
        'backend': 'word-punctuation-v1 (explicit in both versions)', 'cache': 'warm filesystem; fresh process for each cold CLI run',
        'implementation_sha256': hashlib.sha256(b''.join(p.relative_to(package_root).as_posix().encode() + p.read_bytes() for p in sorted(package_root.rglob('*.py')))).hexdigest(),
        'corpus': f'authored deterministic source v1, {len(TEXT.encode())}-byte shared source shape', 'repeats': repeats, 'workloads': {}}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for count in (1, 100, 1000):
            for i in range(count):
                path = root / str(i) / 'SKILL.md'
                path.parent.mkdir(exist_ok=True)
                path.write_text(TEXT)
            paths = sorted(root.glob('*/SKILL.md'))
            # A warm-up is excluded from all warm timings.
            api.validate(paths[0], skip_dirname_check=True)
            for mode in ('cold-cli', 'warm-batch', 'graph-report'):
                timings = []
                for _ in range(repeats):
                    start = time.perf_counter()
                    if mode == 'cold-cli':
                        if modern:
                            command = [sys.executable, '-m', package, str(root), '--skip-dirname-check', '--format', 'json']
                        else:
                            bootstrap = 'import skillcheck.tokenizer as t; t._tiktoken_available=True; t._tiktoken_enc=None; from skillcheck.cli import main; main()'
                            command = [sys.executable, '-c', bootstrap, str(root), '--skip-dirname-check', '--format', 'json']
                        process = subprocess.run(command, capture_output=True, timeout=60)
                        if process.returncode:
                            raise RuntimeError(process.stderr.decode())
                    elif mode == 'graph-report' and modern:
                        documents = [parser.parse(p) for p in paths]
                        reports = [api.validate(doc, skip_dirname_check=True) for doc in documents]
                        for doc in documents:
                            graph.extract_graph_heuristic(doc)
                        formatter._format_json(reports, api.__version__)
                    else:
                        reports = [api.validate(p, skip_dirname_check=True) for p in paths]
                        if mode == 'graph-report':
                            for p in paths:
                                graph.extract_graph_heuristic(parser.parse(p))
                            for p in paths:
                                parser.parse(p)  # Legacy score-report parse, measured in the baseline pipeline.
                        formatter._format_json(reports, api.__version__)
                    timings.append(time.perf_counter() - start)
                results['workloads'][f'{mode}-{count}'] = {'seconds': timings, 'median': statistics.median(timings), 'spread': max(timings) - min(timings)}
        tracemalloc.start()
        reports = [api.validate(p, skip_dirname_check=True) for p in paths]
        formatter._format_json(reports, api.__version__)
        results['peak_python_bytes_1000'] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        # Wide Markdown references, a near-limit JSON import, and 1000 historical entries.
        stress = root / 'stress'
        stress.mkdir()
        references = ''.join(f'[ref{i}](ref{i}.md)\n' for i in range(500))
        (stress / 'SKILL.md').write_text(TEXT + references)
        for i in range(500):
            (stress / f'ref{i}.md').write_text('Reference content.\n')
        results['large_references'] = measure(lambda: api.validate(stress / 'SKILL.md', skip_dirname_check=True), repeats)
        ingest = importlib.import_module(package + '.agents._ingest')
        payload = '{"probe":true}' + ' ' * (ingest.MAX_INGEST_BYTES - 100)
        results['near_limit_import'] = measure(lambda: ingest.decode_json_or_raise(payload, ValueError), repeats)
        results['near_limit_import_bytes'] = len(payload)
        history = importlib.import_module(package + '.core.history')
        skill = parser.parse(stress / 'SKILL.md')
        report = api.validate(stress / 'SKILL.md', skip_dirname_check=True)
        entry = history.build_entry(skill, report, history.ValidationModes(True, False, False), history.RunAgents(None, None), 0, api.__version__)
        ledger = history.Ledger(1, 'SKILL.md', (entry,) * 1000)
        ledger_path = root / 'growing-ledger.json'
        history.save_ledger(ledger_path, ledger)
        results['legacy_history_1000_read'] = measure(lambda: history.load_ledger(ledger_path), repeats)
        if modern:
            storage = importlib.import_module(package + '.storage')
            store = root / 'immutable-history'
            started = time.perf_counter()
            for index in range(1000):
                storage.put_record(store, {'schema_version': 2, 'kind': 'validation-history', 'run_id': str(index),
                    'bundle_sha256': 'a' * 64, 'configuration_sha256': 'b' * 64, 'entry': history._entry_to_dict(entry)})
            results['immutable_history_1000_write_seconds'] = time.perf_counter() - started
            results['immutable_history_1000_read'] = measure(lambda: history.load_ledger(store), repeats)
    return results


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument('--package', default='tracemantle')
    args.add_argument('--repeats', type=int, default=3)
    args.add_argument('--output', type=Path, required=True)
    selected = args.parse_args()
    report = benchmark(selected.package, selected.repeats)
    selected.output.write_text(json.dumps(report, indent=2) + '\n')
    print(selected.output)


if __name__ == '__main__':
    main()
