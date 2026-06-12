"""Control-flow and utility nodes."""
from __future__ import annotations

import time

from engine.registry import ParamSpec, register


@register(
    type="control.start",
    label="Start",
    category="Control",
    description="Entry point of the workflow. Exactly one per flow.",
)
def start(ctx, params, node):
    return "next"


@register(
    type="control.log",
    label="Log Message",
    category="Control",
    params=[ParamSpec("message", "Message", "text", placeholder="Supports {{variables}}")],
    description="Write a message to the run log.",
)
def log(ctx, params, node):
    ctx.log(params.get("message", ""), "info", node_id=node["id"])
    return "next"


@register(
    type="control.delay",
    label="Wait / Delay",
    category="Control",
    params=[ParamSpec("seconds", "Seconds", "number", default=1)],
    description="Pause execution for a number of seconds.",
)
def delay(ctx, params, node):
    secs = float(params.get("seconds", 1) or 0)
    # Sleep in small slices so cancellation stays responsive.
    end = time.time() + secs
    while time.time() < end and not ctx.cancelled:
        time.sleep(min(0.2, end - time.time()))
    return "next"


@register(
    type="control.set_variable",
    label="Set Variable",
    category="Control",
    params=[
        ParamSpec("name", "Variable name", "string", placeholder="myVar"),
        ParamSpec("value", "Value", "text", placeholder="Supports {{variables}}"),
    ],
    description="Store a value in a variable for later steps to use as {{name}}.",
)
def set_variable(ctx, params, node):
    name = (params.get("name") or "").strip()
    if name:
        ctx.vars[name] = params.get("value", "")
        ctx.log(f"{name} = {ctx.vars[name]!r}", "info", node_id=node["id"])
    return "next"


@register(
    type="control.if",
    label="If / Condition",
    category="Control",
    params=[
        ParamSpec("left", "Left value", "string", placeholder="{{count}}"),
        ParamSpec(
            "op", "Operator", "select", default="==",
            options=["==", "!=", ">", "<", ">=", "<=", "contains", "is empty"],
        ),
        ParamSpec("right", "Right value", "string", placeholder="10"),
    ],
    outputs=["true", "false"],
    description="Branch the flow. Connect the True and False outputs to different steps.",
)
def if_node(ctx, params, node):
    left = params.get("left", "")
    right = params.get("right", "")
    op = params.get("op", "==")

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    result = False
    if op == "==":
        result = str(left) == str(right)
    elif op == "!=":
        result = str(left) != str(right)
    elif op == "contains":
        result = str(right) in str(left)
    elif op == "is empty":
        result = str(left).strip() == ""
    else:
        a, b = num(left), num(right)
        if a is not None and b is not None:
            result = {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]

    ctx.log(f"Condition ({left} {op} {right}) -> {result}", "info", node_id=node["id"])
    return "true" if result else "false"


@register(
    type="control.loop",
    label="Loop (For Each)",
    category="Control",
    params=[
        ParamSpec("list_var", "List variable to iterate", "string", placeholder="rows"),
        ParamSpec("item_var", "Current item variable", "string", default="item"),
    ],
    outputs=["body", "done"],
    description=(
        "Iterate over each item in a list variable. Wire 'body' to the steps to "
        "repeat, then connect the LAST body step back to this node. Use {{item}} "
        "(and {{item_index}}) inside the body. When the list is exhausted, 'done' fires."
    ),
)
def loop(ctx, params, node):
    nid = node["id"]
    state = ctx.node_state.setdefault(nid, {"i": 0, "items": None})

    # Load the list once, on first entry.
    if state["items"] is None:
        raw = ctx.vars.get((params.get("list_var") or "").strip(), [])
        if isinstance(raw, list):
            state["items"] = raw
        elif isinstance(raw, (str, bytes)) or not hasattr(raw, "__iter__"):
            state["items"] = [raw]
        else:
            state["items"] = list(raw)

    items = state["items"]
    i = state["i"]
    item_var = (params.get("item_var") or "item").strip()

    if i < len(items):
        ctx.vars[item_var] = items[i]
        ctx.vars[item_var + "_index"] = i
        state["i"] = i + 1
        ctx.log(f"Iteration {i + 1}/{len(items)}", "info", node_id=nid)
        return "body"

    # Done: reset so a re-entry (e.g. nested in an outer loop) starts fresh.
    ctx.node_state.pop(nid, None)
    ctx.log(f"Loop finished ({len(items)} items)", "info", node_id=nid)
    return "done"
