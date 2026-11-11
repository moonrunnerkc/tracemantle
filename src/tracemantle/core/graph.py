"""Capability graph extraction from a parsed skill, heuristic or agent-supplied.

The heading and list vocabularies the heuristic relies on live in
graph_markdown; the data model lives in graph_model.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from typing import Literal

from tracemantle.core.graph_markdown import (
    IMPERATIVE_VERBS,
    INPUT_SECTION_ALIASES,
    OUTPUT_SECTION_ALIASES,
    _infer_input_kind,
    _infer_output_kind,
    _is_imperative_heading,
    _is_input_section_heading,
    _is_output_section_heading,
    _named_list_items,
    _sectionize,
    _strip_section_prefix,
    extract_backtick_refs,
)
from tracemantle.core.graph_model import (
    Capability,
    CapabilityGraph,
    Edge,
    Input,
    Output,
)
from tracemantle.io_limits import MAX_GRAPH_NODES
from tracemantle.parser import ParsedSkill

# Re-exported so ``from tracemantle.core.graph import CapabilityGraph`` and the
# vocabulary names keep working after the model and vocabularies moved out.
__all__ = [
    "Capability",
    "CapabilityGraph",
    "Edge",
    "Input",
    "Output",
    "IMPERATIVE_VERBS",
    "INPUT_SECTION_ALIASES",
    "OUTPUT_SECTION_ALIASES",
    "extract_backtick_refs",
    "extract_graph_agent",
    "extract_graph_heuristic",
]

# ---------------------------------------------------------------------------
# ID generation: content-derived, deterministic, stable across runs
# ---------------------------------------------------------------------------


class GraphLimitError(ValueError):
    """The heuristic graph exceeds its bounded work budget."""


def _make_id(node_type: str, name: str, line: int | None) -> str:
    """Return an 8-hex-char ID derived from node_type, name, and line.

    Two calls with identical arguments always return the same value. No
    timestamps, no randomness.
    """
    raw = f"{node_type}:{name}:{line if line is not None else -1}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def _document_order(node: Capability | Input | Output) -> tuple[int, str]:
    """Sort key: source line, with line-less frontmatter tools first, then name."""
    return (node.line if node.line is not None else -1, node.name)


def extract_graph_heuristic(skill: ParsedSkill) -> CapabilityGraph:
    """Extract a CapabilityGraph from a ParsedSkill using markdown heuristics.

    Pure function: no I/O, no randomness, no mutation after construction.
    Two calls with the same skill produce equal, hash-equal graphs with
    identical tuple ordering.

    Algorithm:
      1. Inputs from frontmatter allowed-tools.
      2. Section-driven inputs and outputs from body headings.
      3. Capabilities from imperative-verb headings outside I/O sections.
      4. Edges from backtick references in capability section bodies.
      5. Sort each collection, build and validate.

    Args:
        skill: Parsed SKILL.md document.

    Returns:
        CapabilityGraph with source="heuristic".
    """
    inputs: list[Input] = []
    outputs: list[Output] = []
    capabilities: list[Capability] = []

    # Step 1: frontmatter-derived tool inputs. Tool IDs are content-hashed on
    # the name alone, so a repeated tool (allowed-tools: [Bash, Bash]) would
    # mint two nodes with the same ID and trip the duplicate-ID check. Dedupe
    # by name first, preserving order.
    allowed_tools = skill.frontmatter.get("allowed-tools", [])
    if isinstance(allowed_tools, (list, tuple)):
        tool_names = [t for t in allowed_tools if isinstance(t, str) and t]
        for tool_name in dict.fromkeys(tool_names):
            iid = _make_id("tool", tool_name, None)
            inputs.append(Input(id=iid, name=tool_name, kind="tool", line=None))

    # name -> id maps; edge pass reads these after the section loop completes.
    input_name_map: dict[str, str] = {inp.name: inp.id for inp in inputs}
    output_name_map: dict[str, str] = {}

    # Capability sections stashed for the deferred edge pass.
    capability_sections: list[tuple[Capability, list[tuple[int, str]]]] = []

    # Steps 2 + 3: scan body sections.
    if len(skill.markdown.visible_lines) > 100000 or len(skill.markdown.headings) > MAX_GRAPH_NODES:
        raise GraphLimitError("Graph exceeds its 100000-line or 10000-heading traversal budget.")
    body_lines = list(skill.markdown.visible_lines)
    for body_line, _level, heading_text, body_content in _sectionize(body_lines):
        line_num = body_line + skill.body_start_line - 1
        content = [(n + skill.body_start_line - 1, text) for n, text in body_content]
        if _is_input_section_heading(heading_text):
            for item_line, name, item in _named_list_items(content):
                input_kind = _infer_input_kind(item)
                iid = _make_id(input_kind, name, item_line)
                inputs.append(Input(id=iid, name=name, kind=input_kind, line=item_line))
                input_name_map[name] = iid

        elif _is_output_section_heading(heading_text):
            for item_line, name, item in _named_list_items(content):
                output_kind = _infer_output_kind(item)
                oid = _make_id(output_kind, name, item_line)
                outputs.append(Output(id=oid, name=name, kind=output_kind, line=item_line))
                output_name_map[name] = oid

        elif _is_imperative_heading(heading_text):
            description = ""
            for _, cline in content:
                stripped = cline.strip()
                if stripped and not re.match(r"^#+\s", cline):
                    description = stripped
                    break
            # Strip section/numeric prefix so stored name matches what an agent
            # would produce. Agents typically drop "1.1" but keep "Phase 1:";
            # we drop both for consistent name-based comparison in divergence
            # analyzers.
            cap_name = _strip_section_prefix(heading_text).strip() or heading_text
            cid = _make_id("capability", cap_name, line_num)
            cap = Capability(
                id=cid, name=cap_name, description=description, line=line_num
            )
            capabilities.append(cap)
            capability_sections.append((cap, content))

    if len(capabilities) + len(inputs) + len(outputs) > MAX_GRAPH_NODES:
        raise GraphLimitError("Graph exceeds the 10000-node traversal budget.")
    # Step 4: edges from backtick references in capability section bodies.
    edges: list[Edge] = []
    targets: tuple[tuple[dict[str, str], Literal["requires", "produces"]], ...] = (
        (input_name_map, "requires"),
        (output_name_map, "produces"),
    )
    for cap, content in capability_sections:
        seen_edge_keys: set[tuple[str, str]] = set()
        for ref in extract_backtick_refs("\n".join(line for _, line in content)):
            for name_map, edge_kind in targets:
                target_id = name_map.get(ref)
                if target_id is not None and (cap.id, target_id) not in seen_edge_keys:
                    edges.append(Edge(source_id=cap.id, target_id=target_id, kind=edge_kind))
                    seen_edge_keys.add((cap.id, target_id))

    # Step 5: sort for determinism.
    return CapabilityGraph(
        capabilities=tuple(sorted(capabilities, key=_document_order)),
        inputs=tuple(sorted(inputs, key=_document_order)),
        outputs=tuple(sorted(outputs, key=_document_order)),
        edges=tuple(sorted(edges, key=lambda e: (e.source_id, e.target_id))),
        source="heuristic",
    )


def extract_graph_agent(skill: ParsedSkill, raw_response: str) -> CapabilityGraph:
    """Extract a CapabilityGraph from an agent JSON response.

    Thin wrapper around parse_graph_response. Returns a graph with
    source="agent". The heuristic extractor is not modified or removed;
    drift detection relies on both extractors coexisting.

    Args:
        skill: ParsedSkill the response was generated for. Used to validate
            that agent-claimed line numbers fall within the actual body.
        raw_response: Raw string from the agent (may include noise, fences,
            prose preamble).

    Returns:
        CapabilityGraph with source="agent".

    Raises:
        GraphParseError: Subclasses GraphJSONError, GraphSchemaError, or
            GraphValueError depending on failure mode. See agents/graph_parser.py.
    """
    from tracemantle.agents.graph_parser import parse_graph_response  # noqa: PLC0415

    graph = parse_graph_response(raw_response, skill)
    offset = skill.body_start_line - 1
    return replace(graph,
        capabilities=tuple(replace(n, line=n.line + offset if n.line is not None else None) for n in graph.capabilities),
        inputs=tuple(replace(n, line=n.line + offset if n.line is not None else None) for n in graph.inputs),
        outputs=tuple(replace(n, line=n.line + offset if n.line is not None else None) for n in graph.outputs))
