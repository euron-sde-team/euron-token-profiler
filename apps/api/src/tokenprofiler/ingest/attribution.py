"""Attribute every span to the agent and the tool it ran under.

An agent span names its agent; a tool span names its tool; everything nested below inherits
the nearest one above it. A model call made inside a `web_search` tool inside the `research`
agent therefore carries both names, which is what makes cost per agent and per tool
additive: each metered span belongs to exactly one agent and at most one tool.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Node:
    span_id: str
    parent_id: str | None
    kind: str
    name: str
    agent_name: str | None = None
    tool_name: str | None = None


def resolve_attribution(nodes: Iterable[Node]) -> dict[str, tuple[str | None, str | None]]:
    """Map span id to (agent, tool). Cycles and missing parents end the walk quietly."""
    by_id = {node.span_id: node for node in nodes}

    def own(node: Node) -> tuple[str | None, str | None]:
        agent = node.agent_name or (node.name if node.kind == "agent" else None)
        tool = node.tool_name or (node.name if node.kind == "tool" else None)
        return agent, tool

    resolved: dict[str, tuple[str | None, str | None]] = {}
    for node in by_id.values():
        agent, tool = own(node)
        seen = {node.span_id}
        cursor = node
        while (agent is None or tool is None) and cursor.parent_id is not None:
            parent = by_id.get(cursor.parent_id)
            if parent is None or parent.span_id in seen:
                break
            seen.add(parent.span_id)
            parent_agent, parent_tool = own(parent)
            agent = agent or parent_agent
            tool = tool or parent_tool
            cursor = parent
        resolved[node.span_id] = (agent, tool)
    return resolved
