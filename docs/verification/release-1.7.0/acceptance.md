# 1.7.0 release verification

## Recovery and release preparation

The owner authorized commit, push, normal merge, stable publication and restoration
of publishing controls. Recovered the existing dirty `main` worktree at
`a5c02e9d7101da85665e75eec471d7dc92bbd4f8`; fetched upstream was identical.
No unrelated changes were present. Before metadata edits, every file digest in
[the implementation manifest](../usability-evidence/source.json) matched and its
canonical manifest digest was
`d203260bb2033485fc55ba72da0a0f4b7a5a4ad835af49c2ec46a79b1c1ecb72`.
That historical manifest identifies the pre-release implementation, not 1.7.0.

GitHub and live PyPI API queries found 1.6.1 latest, with no 1.7.0 version or tag.
The backward-compatible opt-in additions warrant minor version 1.7.0. Package,
API, installed skill, lock metadata and active installation/Action/pre-commit
examples were synchronized; historical verification records were retained.
The changelog was fully promoted before tagging and the release checker passed.
A temporary Git test confirmed release-note automation leaves newer main entries
untouched when the released tag already contains its version heading.

Review found no committed private keys, accidental credential material, weakened
trust checks or runtime dependency changes. Test keys are generated in temporary
directories. The CI approval job now installs its system tools and fails if any
signature/producer test skips; it also runs the Action from the checked-out source.
The implementation's signed deterministic helper tests are workflow mechanics,
not a real agent evaluation or a production signing deployment.

The README is 305 whitespace-delimited words. Its first command block installs
1.7.0, validates one file and links the first-file example. The displayed result
explains heuristic advice and the live-agent limitation. Five task links expose
CI, imports, approval and troubleshooting without requiring them for validation.
This is an editorial walkthrough, not a human usability study.

Publication identities, exact-source CI, artifact hashes and public-install
acceptance will be recorded after the release workflow settles. Publishing
controls remain disabled during preparation.
