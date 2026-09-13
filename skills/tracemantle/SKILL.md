---
name: tracemantle
description: Validates and scores SKILL.md files against the agentskills.io specification; use when linting skills for cross-agent compatibility, description quality, or capability graph structure.
version: "1.6.1"
author: "moonrunnerkc, Aftermath Technologies Ltd"
---

TraceMantle is a local static analyzer for SKILL.md files. It validates frontmatter structure, scores advisory description features, checks file references, and extracts a capability graph from heading and backtick-reference patterns. Run it before committing a skill, plugging it into CI, or publishing to a skill registry.

## Prerequisites

- path - the SKILL.md file or directory to validate
- prompt.txt - file path for a saved agent prompt (critique or graph extraction)
- response.json - file path for an agent-provided JSON response

## Validate a skill

Pass `path` to `tracemantle` for a full structural check against the agentskills.io specification. Validates name constraints, description quality, body sizing, file references, and cross-agent compatibility. The `validation report` is written to stdout. Exit codes: 0 no errors, 1 errors found, 2 input error (missing file), 3 symbolic passed but semantic critique flagged errors.

```bash
tracemantle <path>
tracemantle <path> --format json
```

## Review a skill with an agent

tracemantle generates a structured critique prompt for `path` and ingests `response.json` as the agent's reply. Save the emitted prompt to `prompt.txt`. The merged `validation report` combines symbolic diagnostics and semantic findings from the critique.

```bash
tracemantle <path> --emit-critique-prompt > prompt.txt
```

Hand `prompt.txt` to your agent. The agent returns JSON. Save the response as `response.json`, then ingest it.

```bash
tracemantle <path> --ingest-critique response.json
```

Pass `--critique-agent codex` or `--critique-agent cursor` to select a prompt variant tuned for that platform. The critique JSON schema is identical across all agent targets.

## Extract a capability graph

tracemantle extracts the `capability graph` from heading structure and backtick references in the body of `path`. Use `prompt.txt` for emitted graph prompts and ingest `response.json` from your agent for richer extraction.

Run graph analysis using the heuristic extractor (no agent needed):

```bash
tracemantle <path> --analyze-graph
```

For richer extraction, emit the graph prompt, run it through your agent, and ingest the response:

```bash
tracemantle <path> --emit-graph-prompt > prompt.txt
tracemantle <path> --ingest-graph response.json
```

Print the graph to stdout:

```bash
tracemantle <path> --emit-graph
tracemantle <path> --emit-graph --format json
```

When both heuristic and agent graphs are available, tracemantle compares them and emits `graph.contradiction.heuristic_disagreement` at error severity for agent-claimed edges that the heuristic does not confirm.

## Check validation history

Append a record to the `validation ledger` for each `--history` run on `path`. The validation history uses immutable per-run records outside the skill bundle, under its parent evidence directory. Legacy history is read without being moved or deleted.

```bash
tracemantle <path> --history
tracemantle <path> --show-history
tracemantle <path> --show-history --format json
```

Each record stores a timestamp, TraceMantle version, bundle/configuration digests, validation modes and per-file results. Comparable prior passing records can produce a history regression warning. Legacy text hashes alone do not establish revision equivalence.

## Compare release evidence

Use `path` with the manifest command to identify skill content and all packaged resources. Import evaluator output into a selected evidence store outside the bundle. Compare baseline and candidate bundles with policy and approved evidence from a trusted base commit. Missing evidence blocks release as unknown; imported model judgments are not proof of observed skill invocation. TraceMantle does not run agents or imported checkers.

```bash
tracemantle manifest <bundle> --format json
tracemantle compare <baseline> <candidate> --trusted-root <trusted-repo> --base-revision <full-commit-sha> --format json
```

## Outputs

- validation report - diagnostic output written to stdout
- capability graph - graph of capabilities, inputs, and outputs extracted from the skill body
- validation ledger - immutable validation records outside the evaluated bundle
