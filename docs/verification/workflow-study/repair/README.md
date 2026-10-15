# Original-version reproduction and repair

The original environment remains an editable clean checkout of
`721845b35ef450ebaaf4c7bfb20990db92d0ed3c`, version 1.7.0. Its Python API was run
against unmodified Trail of Bits SARIF sources at
`1f68e03536f7980d4c0e6869596f708043a19443`. `original-reproduction.json` retains
the diagnostics and manifest. Independently tokenizing
`[helper]({baseDir}/resources/sarif_helpers.py)` returns zero resources and
`uncertain=true`: removing the illustrative examples would not repair templates.

SKILL.md line 91 contrasts scanner checkout locations `/path/to/project/` and
`/github/workspace/`. Lines 260–263 explain why `auth/login.py` and
`admin/login.py` must have different deduplication keys. These are explanations
about analyzed projects, not instructions to open packaged files. The actual
helper and query links occur at lines 80–82. The retained upstream bytes and
license are in `integrations/sarif/vendor`, with per-file SHA-256 provenance.

Before implementation, the first 18 new regressions all failed
(`regressions-before.txt`). The four authentic cases failed on definite error
claims; template API cases failed because the interpretation did not exist.
The after log covers 132 focused tests, including three additional provenance
and dependency-invalidation tests added after implementation. Those three were
not demonstrated failing before the repair. Existing inline token-kind tests
were updated from `resource` to `mention` for the intentional contract change;
explicit-link expectations were preserved.

The repair leaves ambiguous inline mentions incomplete. It neither infers
arbitrary author intent nor grants an ignore/coverage override. Skill-root
interpretation is an explicit Python setting, bound in the consumer checker.
No candidate metadata can select it. The raw `{baseDir}` spelling remains part
of token identity. Explicit links, including transitive links, still diagnose
missing resources and boundary escapes. Template support does not establish
complete dependency coverage for the authentic SARIF bundle.
