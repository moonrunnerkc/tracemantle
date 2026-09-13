# Post-release performance verification

Five repetitions, CPython 3.12.13, macOS 26.6.2 arm64. Both checkouts already have the shared parsed model. The word/punctuation backend is explicit; filesystem cache is warm and each cold CLI sample starts a fresh process. Times include reporting. No historical speedup is treated as newly reproduced.

| Workload | Baseline median ms | Corrected median ms | Change | Corrected spread ms |
|---|---:|---:|---:|---:|
| cold-cli-1 | 57.969 | 61.951 | +6.9% | 4.754 |
| warm-batch-1 | 0.233 | 0.220 | -5.8% | 0.415 |
| graph-report-1 | 0.237 | 0.237 | +0.2% | 0.141 |
| cold-cli-100 | 97.732 | 102.821 | +5.2% | 2.461 |
| warm-batch-100 | 19.847 | 20.906 | +5.3% | 1.424 |
| graph-report-100 | 17.808 | 19.357 | +8.7% | 1.199 |
| cold-cli-1000 | 487.618 | 494.319 | +1.4% | 18.635 |
| warm-batch-1000 | 208.687 | 210.404 | +0.8% | 17.897 |
| graph-report-1000 | 192.790 | 194.299 | +0.8% | 10.411 |
| large_references | 38.948 | 36.323 | -6.7% | 4.126 |
| near_limit_import | 1.207 | 1.232 | +2.1% | 0.029 |
| legacy_history_1000_read | 6.750 | 6.969 | +3.3% | 2.383 |
| immutable_history_1000_read | 36.701 | 36.410 | -0.8% | 9.766 |

Peak Python allocations for 1,000 results: 5,798,734 to 5,802,840 bytes (+0.07%). Every measured median stays within the 10% regression budget. This corpus does not establish production-wide timing or total process RSS.

The supplemental [Markdown benchmark](benchmark-markdown.py) exercises 1,000 inline code examples, 1,000 indented directives, 1,000 real links and 1,000 explicit inline resource paths. It retains exact corpus bytes/hash, all samples, spread and traced peak allocations in the baseline/current Markdown JSON files. Resource counts change intentionally from 4,000 (including false code dependencies) to 2,000 real dependencies.
Its median changes from 16.326 to 14.870 ms (-8.9%); corrected spread is 0.682 ms. Peak Python allocations change from 1,190,161 to 2,828,807 bytes. Masking preserves source offsets and needs temporary span storage. Processing remains bounded by the source limits.

Commands (baseline worktree is detached at `0c18c10`):

```bash
PYTHONPATH=/tmp/tracemantle-audit-baseline/src /tmp/tracemantle-audit-312/bin/python /tmp/tracemantle-audit-baseline/scripts/benchmark.py --repeats 5 --output docs/verification/audit-1.6.1/baseline-performance.json
/tmp/tracemantle-audit-312/bin/python scripts/benchmark.py --repeats 5 --output docs/verification/audit-1.6.1/current-performance.json
PYTHONPATH=/tmp/tracemantle-audit-baseline/src /tmp/tracemantle-audit-312/bin/python docs/verification/audit-1.6.1/benchmark-markdown.py > docs/verification/audit-1.6.1/baseline-markdown.json
/tmp/tracemantle-audit-312/bin/python docs/verification/audit-1.6.1/benchmark-markdown.py > docs/verification/audit-1.6.1/current-markdown.json
```
