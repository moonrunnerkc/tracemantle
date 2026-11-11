"""Emit modes: print a prompt, graph, packet or activation report instead of
validating. Each reads its batch through cli_inputs.parse_batch and exits 1
when any file could not be parsed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tracemantle import __version__
from tracemantle.agents import get_agent_prompt, get_graph_prompt
from tracemantle.cli_inputs import parse_batch
from tracemantle.core import (
    extract_graph_heuristic,
    generate_activation_hypotheses,
    render_activation_json,
    render_activation_markdown,
    render_activation_text,
    render_graph_json,
    render_graph_text,
)
from tracemantle.core.graph import GraphLimitError
from tracemantle.display import terminal
from tracemantle.parser import ParseError


def _emit_documents(paths: list[Path], fmt: str, mode: str, agent_id: str = "claude") -> None:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path, skill in parse_batch(paths):
        if isinstance(skill, ParseError):
            errors.append({"path": str(path), "error": str(skill)})
            continue
        if mode == 'graph':
            try:
                graph = extract_graph_heuristic(skill)
            except GraphLimitError as exc:
                errors.append({"path": str(path), "error": str(exc)})
                continue
            item = json.loads(render_graph_json(graph))
            rendered = render_graph_text(graph)
        else:
            prompt = (get_agent_prompt(agent_id) if mode == 'critique' else get_graph_prompt(agent_id)).render(skill)
            item = {"prompt": prompt}
            rendered = prompt
        items.append({"path": str(path), **item})
        if fmt != 'json':
            if len(paths) > 1:
                print(terminal(f"# === tracemantle:{'critique-prompt' if mode == 'critique' else mode}:{path} ==="))
            # Preserve generated layout while making all other controls inert.
            print("\n".join(terminal(line) for line in rendered.split('\n')))
    if fmt == 'json':
        payload: dict[str, Any] = {"tool": "TraceMantle", "version": __version__, "schema_version": 2, "mode": mode}
        if len(items) == 1 and len(paths) == 1:
            payload.update(items[0])
        else:
            payload['results'] = items
        if errors:
            payload['errors'] = errors
        print(json.dumps(payload, indent=2))
    else:
        for error in errors:
            print(terminal(f"Error: {error['path']}: {error['error']}"), file=sys.stderr)
    if errors:
        sys.exit(1)


def emit_graph(paths: list[Path], fmt: str) -> None:
    _emit_documents(paths, fmt, 'graph')


def emit_critique_prompts(paths: list[Path], fmt: str, agent_id: str = 'claude') -> None:
    _emit_documents(paths, fmt, 'critique', agent_id)


def emit_graph_prompts(paths: list[Path], fmt: str, agent_id: str = 'claude') -> None:
    _emit_documents(paths, fmt, 'graph-prompt', agent_id)


def emit_agent_reason_packet(paths: list[Path], fmt: str, critique_agent: str, graph_agent: str) -> None:
    """Print a combined critique and graph prompt packet for in-agent execution."""
    packets: list[dict[str, str]] = []
    errors = []
    for path, skill in parse_batch(paths):
        if isinstance(skill, ParseError):
            errors.append({'path': str(path), 'error': str(skill)})
            continue
        packets.append({
            "path": str(path),
            "critique_prompt": get_agent_prompt(critique_agent).render(skill),
            "graph_prompt": get_graph_prompt(graph_agent).render(skill),
        })

    if fmt == "json":
        print(json.dumps({'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2, "agent_reason": packets, 'errors': errors}, indent=2))
        if errors:
            sys.exit(1)
        return

    for error in errors:
        print(terminal(f"Error: {error['path']}: {error['error']}"), file=sys.stderr)
    for index, raw_packet in enumerate(packets, start=1):
        packet = {key: '\n'.join(terminal(line) for line in value.split('\n')) if key.endswith('_prompt') else terminal(value) for key, value in raw_packet.items()}
        if len(packets) > 1:
            print(f"# === tracemantle:agent-reason:{packet['path']} ===")
        if fmt == "md":
            print(f"# Agent Reason Packet {index}\n")
            print(f"Path: `{packet['path']}`\n")
            print("## Critique prompt\n")
            print(f"```text\n{packet['critique_prompt']}\n```\n")
            print("## Graph prompt\n")
            print(f"```text\n{packet['graph_prompt']}\n```")
        elif fmt == "agent":
            print("tracemantle agent-reason packet")
            print(f"path: {packet['path']}")
            print("task: run both prompts, save each JSON response, then invoke tracemantle with --ingest-critique and --ingest-graph")
            print("critique_prompt:")
            print(packet["critique_prompt"])
            print("graph_prompt:")
            print(packet["graph_prompt"])
        else:
            print("Critique prompt:")
            print(packet["critique_prompt"])
            print("\nGraph prompt:")
            print(packet["graph_prompt"])

    if errors:
        sys.exit(1)


def emit_activation(paths: list[Path], fmt: str) -> None:
    """Print activation hypotheses for each path and exit 0."""
    multiple = len(paths) > 1
    reports = []
    errors = []
    for path, skill in parse_batch(paths):
        if isinstance(skill, ParseError):
            errors.append({'path': str(path), 'error': str(skill)})
        else:
            reports.append((path, generate_activation_hypotheses(skill)))
    if fmt == 'json':
        payload: dict[str, Any] = {'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2}
        if multiple or not reports:
            payload['activation_reports'] = [json.loads(render_activation_json(report)) for _, report in reports]
        else:
            payload.update(json.loads(render_activation_json(reports[0][1])))
        if errors:
            payload['errors'] = errors
        print(json.dumps(payload, indent=2))
    else:
        for path, report in reports:
            if multiple:
                print(terminal(f'# === tracemantle:activation:{path} ==='))
            print(render_activation_markdown(report) if fmt == 'md' else render_activation_text(report))
        for error in errors:
            print(terminal(f"Error: {error['path']}: {error['error']}"), file=sys.stderr)
    if errors:
        sys.exit(1)
