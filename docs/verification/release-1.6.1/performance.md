# Patch performance verification

Five repetitions on CPython 3.12.13/macOS 26.6.2 arm64 compare audited `79f8fdf5dfe4f4004eb5926359c7b13c44fc8519` with the corrected source. Both already reuse the shared parsed model. Heuristic counting, warm filesystem caches and fresh processes for cold CLI runs match the existing benchmark. The first baseline (`baseline-performance.json`) overlapped the initial regressions; the paired results below ran serially after all suites and builds finished. All samples, spreads, corpus and implementation hashes are retained. This is local timing evidence, not a production guarantee or a newly reproduced historical 25% speedup.

## Representative workload

| Workload | Baseline ms | Corrected ms | Change | Spread ms |
|---|---:|---:|---:|---:|
| cold-cli-1 | 57.077 | 56.905 | -0.3% | 1.644 |
| warm-batch-1 | 0.221 | 0.221 | +0.0% | 0.394 |
| graph-report-1 | 0.220 | 0.220 | +0.3% | 0.132 |
| cold-cli-100 | 96.848 | 96.656 | -0.2% | 1.536 |
| warm-batch-100 | 19.916 | 19.747 | -0.8% | 1.147 |
| graph-report-100 | 18.381 | 18.092 | -1.6% | 0.437 |
| cold-cli-1000 | 459.916 | 459.602 | -0.1% | 3.772 |
| warm-batch-1000 | 197.210 | 197.082 | -0.1% | 3.613 |
| graph-report-1000 | 183.559 | 180.838 | -1.5% | 6.302 |
| large_references | 33.323 | 32.991 | -1.0% | 2.461 |
| near_limit_import | 1.145 | 1.157 | +1.1% | 0.053 |
| legacy_history_1000_read | 6.824 | 6.779 | -0.7% | 2.348 |
| immutable_history_1000_read | 33.751 | 33.966 | +0.6% | 9.915 |

Raw reports: [baseline-performance-idle.json](baseline-performance-idle.json), [current-performance.json](current-performance.json).

## Setext and adjacent block workload

| Workload | Baseline ms | Corrected ms | Change | Spread ms |
|---|---:|---:|---:|---:|
| setext-links-1000 | 7.585 | 10.732 | +41.5% | 2.344 |
| multiline-heading-spans-1000 | 12.203 | 12.706 | +4.1% | 0.282 |
| long-underlines | 23.235 | 0.345 | -98.5% | 0.038 |
| near-thematic-breaks | 4.624 | 9.297 | +101.1% | 0.183 |

Raw reports: [baseline-setext.json](baseline-setext.json), [current-setext.json](current-setext.json).

## Preserved parser workload

| Workload | Baseline ms | Corrected ms | Change | Spread ms |
|---|---:|---:|---:|---:|
| escaped-and-list-links | 19.268 | 19.997 | +3.8% | 1.061 |
| long-backslash-runs | 49.722 | 49.811 | +0.2% | 0.740 |
| unmatched-delimiter-lengths | 31.160 | 31.403 | +0.8% | 1.074 |

Raw reports: [baseline-parser.json](baseline-parser.json), [current-parser.json](current-parser.json).

The representative graph/report and preserved escaped-delimiter workloads meet the 10% median budget. Discovering 1,000 formerly hidden Setext dependencies costs 3.15 ms (+41.5%) on the heading-heavy corpus. Rejecting long near-thematic lines costs 4.67 ms (+101.1%) on 200 KiB of adversarial markers because whitespace-separated homogeneous markers must now be checked. These focused correctness costs are below 11 ms per workload, with source limits unchanged. Valid multiline heading spans still exclude all 1,000 example links. The 500,000-character valid underline now avoids irrelevant inline masking and exposes its helper. Parser JSON retains traced peak Python allocations; these are not total process RSS.

Reproduce using `scripts/benchmark.py --repeats 5 --output PATH`, `docs/verification/release-1.6.1/benchmark-setext.py`, and the existing `docs/verification/audit-1.6.1/benchmark-boundaries.py`. Run each serially with the same constrained 3.12 interpreter. For the audited source only, select the detached worktree with `PYTHONPATH=/tmp/tracemantle-setext-baseline/src`; the corrected source uses its editable development environment. This source selection is only for comparative benchmarks. Published acceptance uses isolated installed distributions without `PYTHONPATH`.
