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

## Final path-compatibility correction

The final source was measured again after preserving parentheses/brackets in explicit resource paths. The same baseline, corpus and five-repeat commands apply, with output destinations `final-performance.json` and `final-markdown.json`. Intermediate measurements above remain associated with the first audit implementation. Timing differences include host variability and are not all attributed to the small compatibility change.

| Workload | Final median ms | Change from baseline | Final spread ms |
|---|---:|---:|---:|
| cold-cli-1 | 54.903 | -5.3% | 0.582 |
| warm-batch-1 | 0.217 | -6.8% | 0.340 |
| graph-report-1 | 0.214 | -9.5% | 0.133 |
| cold-cli-100 | 93.807 | -4.0% | 1.412 |
| warm-batch-100 | 19.319 | -2.7% | 0.906 |
| graph-report-100 | 18.025 | +1.2% | 13.659 |
| cold-cli-1000 | 453.864 | -6.9% | 28.474 |
| warm-batch-1000 | 192.288 | -7.9% | 4.348 |
| graph-report-1000 | 175.016 | -9.2% | 3.366 |
| large_references | 32.058 | -17.7% | 1.721 |
| near_limit_import | 1.164 | -3.6% | 0.035 |
| legacy_history_1000_read | 6.566 | -2.7% | 2.268 |
| immutable_history_1000_read | 32.851 | -10.5% | 10.062 |

All final medians remain within the 10% regression budget. The code-context workload retains exactly 2,000 real dependencies, at 15.485 ms median (-5.2%) with 0.531 ms spread. Its peak Python allocation is 2,828,847 bytes; the 1,000-skill report peak is 5,801,900 bytes. No new performance exception was needed.

## YAML scalar conversion correction

The first scalar-corrected run (`scalar-performance.json`) overlapped clean artifact installation. Compared with the original baseline, unchanged legacy/immutable history reads were 27.4%/24.0% slower. No history implementation changed. To separate host/filesystem variability from the parser correction, both baseline and candidate were rerun serially after other verification finished, with five repetitions each. All original samples are retained; the paired repeat is in `baseline-performance-repeat.json` and `scalar-performance-repeat.json`.

| Workload | Repeated baseline ms | Scalar-corrected median ms | Change | Corrected spread ms |
|---|---:|---:|---:|---:|
| cold-cli-1 | 55.236 | 55.149 | -0.2% | 0.872 |
| warm-batch-1 | 0.221 | 0.221 | +0.1% | 0.404 |
| graph-report-1 | 0.223 | 0.219 | -1.7% | 0.141 |
| cold-cli-100 | 94.773 | 94.243 | -0.6% | 2.911 |
| warm-batch-100 | 19.071 | 19.095 | +0.1% | 1.104 |
| graph-report-100 | 17.291 | 17.354 | +0.4% | 0.653 |
| cold-cli-1000 | 444.123 | 446.716 | +0.6% | 4.927 |
| warm-batch-1000 | 194.702 | 190.054 | -2.4% | 4.047 |
| graph-report-1000 | 171.943 | 173.411 | +0.9% | 4.111 |
| large_references | 31.506 | 31.410 | -0.3% | 3.271 |
| near_limit_import | 1.144 | 1.154 | +0.8% | 0.025 |
| legacy_history_1000_read | 6.313 | 6.539 | +3.6% | 2.249 |
| immutable_history_1000_read | 32.255 | 32.479 | +0.7% | 9.910 |

The isolated paired repeat keeps every median within budget (largest increase 3.6%). Peak Python allocation for 1,000 reports is 5,802,024 to 5,801,101 bytes. The unchanged history code and disappearing outlier support host/filesystem contention as the explanation for the earlier sample, rather than a new history regression. The Markdown tokenizer bytes are unchanged from `final-markdown.json`; its code-context measurement remains applicable.


## Escaped delimiters and JSON overflow correction

The new baseline is `5034d626e73952c44b48025727c6e2fde6568f24`, matching the reported audit. Both source versions already reuse the parsed document, so no new 25% repeated-parse speedup is claimed. Five repetitions on CPython 3.12.13/macOS arm64 use the existing `scripts/benchmark.py`, explicit heuristic backend, warm filesystem and fresh processes for cold CLI. Each pair ran serially after the local suites/builds finished.

The initial pair (`boundaries-baseline-performance.json`, `boundaries-performance.json`) exceeded 10% for cold CLI at one source, warm/graph work at one source and graph/report at 100 sources. Single-source warm medians rose from about 0.22 to 0.36/0.39 ms. A second pair reversed execution order to check timing variability; all its medians meet the 10% target. Both pairs, complete samples and spreads are retained. This repeat does not erase the initial measurements or establish a production-wide guarantee.

| Workload | Repeated baseline ms | Corrected ms | Change | Corrected spread ms |
|---|---:|---:|---:|---:|
| cold-cli-1 | 55.983 | 56.580 | +1.1% | 25.975 |
| warm-batch-1 | 0.222 | 0.221 | -0.3% | 0.403 |
| graph-report-1 | 0.218 | 0.224 | +2.8% | 0.136 |
| cold-cli-100 | 95.283 | 95.377 | +0.1% | 1.715 |
| warm-batch-100 | 19.240 | 19.537 | +1.5% | 1.018 |
| graph-report-100 | 17.516 | 18.190 | +3.8% | 1.495 |
| cold-cli-1000 | 469.996 | 451.729 | -3.9% | 22.035 |
| warm-batch-1000 | 193.255 | 197.661 | +2.3% | 9.124 |
| graph-report-1000 | 175.856 | 189.461 | +7.7% | 4.760 |
| large_references | 31.804 | 33.750 | +6.1% | 2.283 |
| near_limit_import | 1.144 | 1.145 | +0.0% | 0.024 |
| legacy_history_1000_read | 6.490 | 7.067 | +8.9% | 2.197 |
| immutable_history_1000_read | 32.495 | 33.482 | +3.0% | 9.846 |

Peak traced Python allocation for 1,000 results: 5,799,127 to 5,801,947 bytes. These are Python allocations, not process RSS.

The unchanged code-context corpus (`benchmark-markdown.py`) retains exactly 2,000 real resources. Its median changes from 16.179 to 16.761 ms (+3.6%), within budget.

The additional `benchmark-boundaries.py` records exact corpus hashes, source hashes, repeated timings and peak allocation for escaped links, nested lists, long backslash runs and unmatched run lengths.

| Parser workload | Baseline ms | Corrected ms | Baseline/corrected resources | Corrected peak bytes |
|---|---:|---:|---:|---:|
| escaped-and-list-links | 13.374 | 19.513 | 0/2000 | 3,002,951 |
| long-backslash-runs | 33.016 | 50.622 | 0/1 | 12,098,295 |
| unmatched-delimiter-lengths | 31.222 | 31.620 | 1/1 | 12,867,987 |

The dependency-heavy escaped/list workload and long-backslash workload exceed the relative 10% target for a correctness reason: the baseline concealed all real dependencies, and the corrected parser counts escape parity and extracts them. Their corrected absolute medians remain below 51 ms on roughly 0.12/1 MiB input. Unmatched delimiters remain within budget. Escape counting, block tracking and delimiter pairing use linear passes with source-size bounds; list-state storage is capped at 32 containers. No parser cap or quality threshold was relaxed.

Reproduce the paired workload with:

```bash
PYTHONPATH=/tmp/tracemantle-boundaries-baseline/src /tmp/tracemantle-audit-312/bin/python scripts/benchmark.py --repeats 5 --output baseline.json
/tmp/tracemantle-audit-312/bin/python scripts/benchmark.py --repeats 5 --output current.json
```

The detached baseline worktree is created at `5034d626e73952c44b48025727c6e2fde6568f24`. Apply the same `PYTHONPATH` selection to `benchmark-markdown.py` and `benchmark-boundaries.py` for the supplemental JSON reports. The repeat files use the same commands in corrected-then-baseline order.
