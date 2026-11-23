# Security policy

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub:
[Report a vulnerability](https://github.com/moonrunnerkc/tracemantle/security/advisories/new)
(repository **Security** tab, **Report a vulnerability**). Private vulnerability
reporting is enabled for this repository. Please do not open a public issue for
an unfixed vulnerability.

Include the TraceMantle version, the command or API call, a minimal input that
reproduces the problem and what you expected instead. This is a single-maintainer
project and no response time is promised.

## Supported versions

Fixes are made on `main` and shipped in a new release. Only the latest published
release receives fixes; earlier releases are not patched.

Python 3.10 is still accepted by the package but is past its upstream end of
life and no longer receives interpreter security fixes. Use a Python version
that [upstream still supports](https://devguide.python.org/versions/).

## What TraceMantle does and does not protect

TraceMantle reads skill files, configuration, evaluator exports and evidence
records as untrusted data. The intended boundaries are:

- It does not execute skill content, embedded instructions, evaluator exports or
  checker files. The one deliberate exception is `import-evidence --adapter PATH`,
  which runs the Python file you name with your privileges and no sandbox.
- Ordinary validation makes no network or model calls. `--tokenizer tiktoken` may
  download its encoding on a cold cache, and `--check-profile-freshness` sends
  HTTP HEAD requests. Both are opt-in.
- Reads are bounded in size, depth and count, and untrusted text is escaped at
  human display boundaries. See [docs/contracts.md](docs/contracts.md).
- Release comparison takes its policy and checker identity from the trusted Git
  revision you select, not from the candidate. Protecting that revision and the
  workflow that selects it is the repository owner's responsibility.

Reports that one of these boundaries can be crossed are in scope: for example a
crafted file that runs code, hangs or exhausts memory, escapes its directory,
injects terminal controls, or lets changed content reuse approved evidence.

The following are limits of the tool, not vulnerabilities:

- A passing validation or a `pass` comparison does not show that a skill behaves
  correctly or safely in a live agent.
- Dependency discovery covers a documented Markdown subset. Helpers reached
  through program imports, shell expansion or files created at run time are not
  discovered, which is why a trusted check declares its own inputs.
- A candidate can change project configuration and frontmatter ignore comments.
  Callers validating contributions they have not reviewed should pass
  `--no-inline-ignores` and an explicit `--config` from trusted tooling.
- A signature or approval shows that a key holder approved a record. It does not
  show that the recorded execution happened.
