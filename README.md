# TraceMantle

TraceMantle checks `SKILL.md` files, the instruction files that tell AI agents when and how to perform a task. Developers who write or maintain agent skills use it to catch broken files before commit or CI. It reports:

- Invalid metadata: malformed YAML frontmatter, or a missing or invalid `name` or `description`.
- Missing files: links in a skill to helpers that do not exist.
- Advice on size, description wording, and documented agent differences. This is guidance, not proof that a skill runs in any agent.

## Quick start

You need Python 3.10 or later; 3.11 or later is [recommended](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/migration.md#python-support). In an empty directory, create a virtual environment, install the published release, and add a directory for the example skill.

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install tracemantle==1.8.0
mkdir hello
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install tracemantle==1.8.0
mkdir hello
```

If PowerShell blocks the activation script, skip it and run `.venv\Scripts\python` and `.venv\Scripts\tracemantle` in place of `python` and `tracemantle`.

Save this file as `hello/SKILL.md`. The directory name must match `name`.

```markdown
---
name: hello
description: Generates conventional commit messages from staged git diffs, enforcing semantic versioning conventions. Use this skill whenever the user needs a commit message, mentions conventional commits, or has staged changes ready to commit.
---

Read the staged diff and write a conventional commit message.
```

Validate it:

```bash
tracemantle hello/SKILL.md
```

```text
✔ PASS  hello/SKILL.md
            · info              description.quality-score  Description quality score: 95/100.

Checked 1 file: 1 passed, 0 failed
```

`PASS` and exit status 0 mean the file has no errors. To check your own skill, substitute its path. Installation downloads packages; default validation then runs locally with no network calls and no account.

## Read results and run common tasks

Errors are defects such as invalid frontmatter or a missing file. Warnings do not fail a run by default. Info lines, including the description score, are heuristic advice.

The exit status decides success: 0 for success, 1 for errors, 2 for a bad path or configuration. With `--strict`, warnings also return 1, even though a file with no errors is still labeled `PASS`.

For example, adding `[commit checklist](checklist.md)` to the skill without creating that file fails with exit status 1 (excerpt):

```text
✗ FAIL  hello/SKILL.md
    line 8  ✗ error             references.broken-link  Referenced file does not exist: 'checklist.md'.
```

Create `hello/checklist.md` or remove the link, then rerun.

| Task | Command |
| --- | --- |
| Check every skill under a directory | `tracemantle hello/` |
| Fail on warnings too | `tracemantle hello/ --strict` |
| Get JSON, with the decision in `gate.passed` | `tracemantle hello/ --format json` |
| List all options | `tracemantle --help` |

Passing static validation does not prove that a skill behaves correctly in a live agent.

## Optional evidence checks

When a helper file changes, an earlier test result may no longer cover the current skill. TraceMantle can identify a skill's content and dependencies and compare imported results against a policy your team approves. The [evidence workflow](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/evidence-workflow.md) covers setup and approval. Imported evidence records what another tool reported; it does not prove correctness on its own.

Selective reuse of earlier results is experimental. In the maintainers' one [workflow study](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/verification/workflow-study/scoped-reuse/case-study.md), it saved no time and justified no more skips than a simple cache.

## Guides and project information

- [Getting started](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/getting-started.md): more examples with expected output.
- [CI setup](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/ci.md): validate skills on pull requests.
- [Evidence checks](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/evidence-workflow.md#detect-helper-changes): detect helper changes.
- [CLI reference](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/generated-reference.md): options, configuration keys, and rule IDs.
- [Troubleshooting](https://github.com/moonrunnerkc/tracemantle/blob/main/docs/getting-started.md#troubleshooting): diagnostics and exit codes.

[Contribute](https://github.com/moonrunnerkc/tracemantle/blob/main/CONTRIBUTING.md) · [Security](https://github.com/moonrunnerkc/tracemantle/blob/main/SECURITY.md) · [Report an issue](https://github.com/moonrunnerkc/tracemantle/issues) · [Changelog](https://github.com/moonrunnerkc/tracemantle/blob/main/CHANGELOG.md) · [MIT license](https://github.com/moonrunnerkc/tracemantle/blob/main/LICENSE)

Maintained by [moonrunnerkc](https://github.com/moonrunnerkc).
