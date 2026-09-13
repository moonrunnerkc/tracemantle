# Synthetic workflow controls

These MIT-licensed, authored fixtures test the trusted comparison workflow. They are not observations of a skill or evaluator execution. The static control binds exact helper and skill bytes to the checker identity in `policy.toml`. Its time is fixed and expires after one year; update it deliberately when repeating acceptance after that boundary.

Dispatch `compare.yml` at a reviewed source revision with the same full SHA as base and candidate, bundle path `tests/fixtures/ci-gates/bundle`, policy path `tests/fixtures/ci-gates/policy.toml` and evidence directory `tests/fixtures/ci-gates/records`. Expect pass. Use the nonexistent evidence directory `tests/fixtures/ci-gates/missing` for the missing-evidence control; expect unknown, exit 4. The real-process temporary-Git tests separately alter candidate policy, checker and helper bytes.
