# Getting started

## Install the published validator

Python 3.10 or later is required. In a clean working directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install tracemantle==1.7.0
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.
This installs 1.7.0. No account, evaluator or evidence policy is needed.
Default validation makes no network calls; package installation downloads packages.

## Validate your first skill

Create `hello/SKILL.md` with this content (the directory must match `name`):

```markdown
---
name: hello
description: Generates conventional commit messages from staged git diffs, enforcing semantic versioning conventions. Use this skill whenever the user needs a commit message, mentions conventional commits, or has staged changes ready to commit.
---

Read the staged diff and write a conventional commit message.
```

Run the first command below from the parent of `hello`. All six transcripts below
were captured from a clean published 1.6.1 installation outside the source checkout,
and checked against the locally built package. Output was redirected, so it has
no terminal colors. `--no-color` produces the same text interactively. Windows
displays backslashes in paths; diagnostic text and exit codes are unchanged.

### A valid skill

```bash
tracemantle hello/SKILL.md
```

```text
✔ PASS  hello/SKILL.md
            · info              description.quality-score  Description quality score: 95/100.

Checked 1 file: 1 passed, 0 failed
```

Exit: `0`.

### Invalid frontmatter

Copy the [invalid fixture](../tests/fixtures/onboarding/invalid/SKILL.md) into `invalid/SKILL.md`. It repeats the YAML `name` key.

```bash
tracemantle invalid/SKILL.md
```

```text
✗ FAIL  invalid/SKILL.md
    line 3  ✗ error             parse.error  Duplicate YAML key 'name'. Keep one value per key.

Checked 1 file: 0 passed, 1 failed
```

Exit: `1`.

### A missing referenced file

Copy the [missing-file fixture](../tests/fixtures/onboarding/missing/SKILL.md) into `missing/SKILL.md`. Its helper link has no target.

```bash
tracemantle missing/SKILL.md
```

```text
✗ FAIL  missing/SKILL.md
            · info              description.quality-score  Description quality score: 95/100.
    line 6  ✗ error             references.broken-link  Referenced file does not exist: 'helper.py'.
              resolved to: helper.py

Checked 1 file: 0 passed, 1 failed
```

Exit: `1`.

### Scan a directory

```bash
tracemantle hello/
```

```text
✔ PASS  hello/SKILL.md
            · info              description.quality-score  Description quality score: 95/100.

Checked 1 file: 1 passed, 0 failed
```

Exit: `0`.

### Warnings allowed

Copy the [warning fixture](../tests/fixtures/onboarding/warning/SKILL.md) into `warning/SKILL.md`. It contains an unrecognized field.

```bash
tracemantle warning/SKILL.md
```

```text
✔ PASS  warning/SKILL.md
    line 4  ⚠ warning           frontmatter.field.unknown  Unknown frontmatter field 'unrecognized-field'. Known fields: allowed-tools, compatibility, description, license, metadata, name.
              unrecognized-field: ...
            · info              description.quality-score  Description quality score: 95/100.

Checked 1 file: 1 passed, 0 failed, 1 warning
```

Exit: `0`.

### Warnings fail in strict mode

```bash
tracemantle warning/SKILL.md --strict
```

```text
✔ PASS  warning/SKILL.md
    line 4  ⚠ warning           frontmatter.field.unknown  Unknown frontmatter field 'unrecognized-field'. Known fields: allowed-tools, compatibility, description, license, metadata, name.
              unrecognized-field: ...
            · info              description.quality-score  Description quality score: 95/100.

Checked 1 file: 1 passed, 0 failed, 1 warning
```

Exit: `1`.

`PASS` describes file errors; strict mode separately rejects warnings, which is
why the final command returns 1 despite the file label. For machine consumers,
`--format json` reports the overall decision in `gate.passed` and `gate.exit_code`.
An info-only description score does not fail strict mode.

## Add CI or track helper changes

Use [CI setup](ci.md) to check pull requests. To determine whether earlier results
still apply after a helper changes, follow the runnable
[helper-change example](evidence-workflow.md#detect-helper-changes).
Importing and approving results are optional, separate tasks covered in that guide.

## Troubleshooting

- **Errors:** fix invalid YAML, missing required fields, invalid names, or missing
  referenced files at the reported location. These block ordinary validation.
- **Heuristic advice:** description quality and size recommendations estimate
  readability and routing cues; they are not measurements of live behavior.
- **Compatibility warnings:** `compat.*` findings identify a profile and its
  limitations. Historical profiles have unverified runtime applicability; see
  [profiles](profiles.md). Explicit strict flags can promote warnings to errors.
- **Exit codes:** validation returns 0 for success, 1 for errors or strict warnings,
  2 for input/configuration failures, and 3 for semantic drift after symbolic
  validation passes. Evidence commands additionally use 4 for unknown and 5 for
  skipped. Do not treat these as success.
- **Configuration:** explicit CLI flags override project settings. Separate
  invocations are required for different discovered project roots. See the
  [configuration reference](generated-reference.md#configuration-keys).
- **Paths:** use the actual skill directory name and keep referenced helper files
  available. Do not suppress reference checks to claim a complete bundle.

Passing file validation does not prove a skill behaves correctly in a live agent.

## Import and approve evidence

The 1.7.0 installation above includes neutral JSON imports and schema-2 automation
approvals. Follow the [evidence workflow](evidence-workflow.md) for manual approval,
protected automation, and the runnable helper-change example. Run example scripts
only from owner-reviewed tooling outside candidate bundles.
