# Bounded check-scope improvement cycle

Starting revision: 7d404ff532669d04f15cfb7e26dc3351a994aa73 (1.7.0 plus unreleased repairs).
Local study worktree and remote study branch matched; worktree was clean.
Earlier protocols, archives and negative measurements remain historical records.

Confirmed by source inspection: ambiguous mentions set Dependencies.complete false;
comparison makes an otherwise passing unchanged manifest unknown. The deployed
workflow registers only report evidence, always runs contract/upstream checks,
and hashes all application sources into report identity. Skipping that report
would omit the current task output. The upstream suite reads SKILL.md, jq-queries.md,
two fixtures and sarif_helpers.py, including commands extracted from documentation.

Implement a narrow, opt-in trusted closed-file scope for deterministic maintenance
checks. Bind its reviewed rationale, assumptions and file set through the existing
profile digest; read it from the selected immutable Git base. Keep legacy policies
conservative. Distinguish manifest resource errors from documentation uncertainty;
never let a declaration hide an explicit broken reference. Add deterministic
observed execution as a check kind, without pretending it is agent behavior.

Register contract and upstream suite separately. Always regenerate both Ruff
exports and Python/jq reports. Hash actual check files, checker, interpreter,
installed tools, configuration and execution assumptions. Unknown external inputs
or unreviewed code changes require execution, not an invented complete scope.
Use the same identity for a small local content cache. Keep approval controls a
separate comparison from ordinary optimization.

Acceptance: demonstrate actual skips, independently rerun every omitted check,
and verify fresh nonempty scanner/report output. Exercise helper, fixtures,
documented commands, transitive/shared inputs, executable mode, checker/context/
scope changes, unresolved inputs and hostile/missing/expired/conflicting evidence.
Candidate policy cannot approve itself. Preserve boundary regressions and legacy
behavior. Run full repository gates and consumer preflight before committing the
prospective three-repetition protocol. Freeze a small known-regression change set,
rotate operational arm order, record decisions before reference execution, retain
all outcomes, and cap scoring at 20 minutes with no live-model calls. Compare full
CLI costs, including output generation and reuse overhead. Prefer the simple cache
if it provides equivalent optimization with less effort.
