"""Workflow executor.

A workflow is a directed graph:
    nodes: [{ "id": str, "type": str, "params": {...} }]
    edges: [{ "source": str, "target": str, "sourceHandle": str | None }]

Execution starts at the `control.start` node and walks the graph one node at a
time. Each node returns a handle name; the executor follows the outgoing edge
whose `sourceHandle` matches (defaulting to "next"). This gives us linear flows
plus branching (If) without a heavyweight graph runtime.

A simple safety cap on total steps prevents runaway loops.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional

from engine import registry
from engine.context import RunContext

MAX_STEPS = 10_000


class WorkflowError(Exception):
    pass


def _index_nodes(nodes: List[dict]) -> Dict[str, dict]:
    return {n["id"]: n for n in nodes}


def _find_start(nodes: List[dict]) -> Optional[dict]:
    for n in nodes:
        if n.get("type") == "control.start":
            return n
    return None


def _next_node_id(edges: List[dict], source_id: str, handle: str) -> Optional[str]:
    # Prefer an edge with a matching sourceHandle; fall back to any edge.
    fallback = None
    for e in edges:
        if e.get("source") != source_id:
            continue
        sh = e.get("sourceHandle") or "next"
        if sh == handle:
            return e.get("target")
        if fallback is None:
            fallback = e.get("target")
    return fallback if handle == "next" else None


def run_workflow(
    workflow: dict,
    on_log: Optional[Callable[[dict], None]] = None,
    run_id: Optional[str] = None,
) -> RunContext:
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    node_by_id = _index_nodes(nodes)

    ctx = RunContext(run_id or uuid.uuid4().hex[:8], on_log=on_log)

    start = _find_start(nodes)
    if not start:
        ctx.log("No Start node found. Add a Start node to begin the flow.", "error")
        return ctx

    ctx.log(f"Run {ctx.run_id} started", "info")
    current_id: Optional[str] = start["id"]
    steps = 0

    try:
        while current_id is not None:
            if ctx.cancelled:
                ctx.log("Run cancelled", "warn")
                break
            steps += 1
            if steps > MAX_STEPS:
                raise WorkflowError(f"Exceeded max steps ({MAX_STEPS}); possible infinite loop.")

            node = node_by_id.get(current_id)
            if node is None:
                raise WorkflowError(f"Edge points to unknown node '{current_id}'.")

            ndef = registry.get(node["type"])
            if ndef is None:
                raise WorkflowError(f"Unknown node type '{node['type']}'.")

            raw_params = node.get("params", {})
            params = ctx.render_params(raw_params)

            ctx.log(f"{ndef.label}", "step", node_id=node["id"])
            try:
                result = ndef.run(ctx, params, node)
            except Exception as ex:  # node-level failure
                ctx.log(f"{ndef.label} failed: {ex}", "error", node_id=node["id"])
                raise

            handle = result if isinstance(result, str) and result else "next"
            current_id = _next_node_id(edges, node["id"], handle)

        ctx.log(f"Run {ctx.run_id} finished", "success")
    except Exception as ex:
        ctx.log(f"Run aborted: {ex}", "error")
    finally:
        ctx.cleanup()

    return ctx
