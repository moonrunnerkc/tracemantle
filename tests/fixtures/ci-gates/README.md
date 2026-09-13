# Synthetic workflow controls

These MIT-licensed, authored fixtures test the trusted comparison workflow. They are not observations of a skill or evaluator execution. The original static control at commit `b9bc5ff3b121fe6ca0d5ed72595c16d6ee68e13e` binds exact helper and skill bytes to the trusted checker. Its time is fixed and expires after one year; update it deliberately when repeating acceptance after that boundary.

For a valid control, dispatch `compare.yml` with that full SHA as both base and candidate, bundle path `tests/fixtures/ci-gates/bundle`, policy path `tests/fixtures/ci-gates/policy.toml` and evidence directory `tests/fixtures/ci-gates/records`. Expect pass. Use the nonexistent evidence directory `tests/fixtures/ci-gates/missing` for the missing-evidence control; expect unknown, exit 4.

The current candidate changes only the helper inside the bundle, marks the candidate policy check optional and replaces its checker with code that raises if executed. Use the original trusted SHA as base and the current reviewed full commit as candidate. Expect unknown, exit 4, with `helper.py` changed and `static-control` required for rerun. Candidate policy/checker bytes cannot replace the immutable base, and the checker exception must never execute. The original approved record is retained unchanged.
