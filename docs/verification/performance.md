# Final local performance measurements

Three repetitions per timing workload, CPython 3.10.14, macOS 26.6.2 arm64. Both implementations explicitly use the unchanged word/punctuation heuristic. Filesystem caches are warm; cold CLI means a fresh Python process, including startup and JSON reporting. This is not a cold OS disk-cache benchmark. The deterministic authored source shape is recorded in the raw reports, along with the package version, implementation digest, individual samples and spread. No persistent cache or analysis concurrency was introduced.

| Workload | SkillCheck 1.5.0 median ms | TraceMantle 1.6.0 median ms | Change |
|---|---:|---:|---:|
| cold-cli-1 | 41.847 | 52.574 | +25.6% |
| warm-batch-1 | 0.340 | 0.332 | -2.2% |
| graph-report-1 | 0.576 | 0.312 | -45.8% |
| cold-cli-100 | 89.589 | 102.562 | +14.5% |
| warm-batch-100 | 28.429 | 27.466 | -3.4% |
| graph-report-100 | 50.963 | 27.036 | -46.9% |
| cold-cli-1000 | 492.126 | 531.683 | +8.0% |
| warm-batch-1000 | 274.947 | 266.785 | -3.0% |
| graph-report-1000 | 505.133 | 253.490 | -49.8% |
| large_references | 12.575 | 26.492 | +110.7% |
| near_limit_import | 1.158 | 1.183 | +2.2% |
| legacy_history_1000_read | 3.918 | 7.743 | +97.6% |

Peak traced Python allocation for 1,000 results/report: 6,338,448 → 6,546,979 bytes (+3.3%). This excludes total process RSS and native-library allocation.

The new immutable store wrote 1,000 complete records in 0.292 s (one provisioning measurement); repeated reads had a 40.33 ms median. Its three raw read samples are retained. New history storage has no equivalent safe concurrent legacy operation.

## Acceptance and correctness costs

The repeated-parse graph/report benchmark improves 49.8% at 1,000 skills, exceeding the 25% target. It reproduces the prior validation parse, graph parse and score-report parse; the current path reuses one parsed document. A real CLI cProfile regression independently asserts exactly one parser call with graph, JSON reporting and history enabled. Warm batches improve at every size and the 1,000-file cold CLI stays within the 10% target.

The small cold CLI workloads exceed the relative 10% target: +10.7 ms at one skill and +13.0 ms at 100. The retained correctness work includes real TOML parsing on Python 3.10, immutable Markdown/document structures, strict JSON/history identity and resource-closure support. Import-time inspection confirms these modules participate in startup; unnecessary product-command imports were already deferred. These absolute startup costs are accepted for the corrected contracts. They are not hidden by excluding startup.

The 500-reference workload increases from 12.57 to 26.49 ms because it now reads bounded transitive Markdown resources and checks closure/cycles instead of only checking reference existence/depth heuristics. The 1,000-entry legacy-history read increases from 3.92 to 7.74 ms because it now validates duplicate keys, bounded JSON structure, timestamps, exact booleans/integers and count consistency. These are documented correctness exceptions to the 10% target. Near-limit imports remain within target. Further optional optimization was stopped once the bounded contracts and reuse target held.

Adversarial regression tests cover expanded aliases, deep YAML/JSON, graph budgets, symlink cycles, bounded reads, malformed records and cross-branch dependency cycles. Measurements apply only to this local authored corpus and environment, not arbitrary production skills or agent task success. The earlier baseline report used an automatically selected optional tokenizer; use the controlled reports for before/after comparisons.

Raw data: [baseline](baseline-controlled-performance.json), [current](current-performance.json), [original baseline](baseline-performance.json).
