"""Node registry.

Every automation step (a "node") registers itself here with a small piece of
metadata that the frontend reads to build the palette and the properties form,
plus a `run` function the executor calls.

A node's `run(ctx, params, inputs)` returns either:
  - None / "next"           -> follow the default outgoing edge
  - a handle name (str)      -> follow the outgoing edge whose sourceHandle matches
                                (used by branching nodes like If)
The node may also write into `ctx.vars` to expose values to later nodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ParamSpec:
    name: str
    label: str
    type: str = "string"          # string | text | number | bool | select
    default: Any = ""
    options: List[str] = field(default_factory=list)   # for type == "select"
    placeholder: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "default": self.default,
            "options": self.options,
            "placeholder": self.placeholder,
        }


@dataclass
class NodeDef:
    type: str
    label: str
    category: str
    run: Callable
    params: List[ParamSpec] = field(default_factory=list)
    # output handles, e.g. ["next"] or ["true", "false"] for branches
    outputs: List[str] = field(default_factory=lambda: ["next"])
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "label": self.label,
            "category": self.category,
            "params": [p.to_dict() for p in self.params],
            "outputs": self.outputs,
            "description": self.description,
        }


_REGISTRY: Dict[str, NodeDef] = {}


def register(
    type: str,
    label: str,
    category: str,
    params: Optional[List[ParamSpec]] = None,
    outputs: Optional[List[str]] = None,
    description: str = "",
):
    """Decorator that registers a node's run function."""
    def deco(fn: Callable) -> Callable:
        _REGISTRY[type] = NodeDef(
            type=type,
            label=label,
            category=category,
            run=fn,
            params=params or [],
            outputs=outputs or ["next"],
            description=description,
        )
        return fn
    return deco


def get(type: str) -> Optional[NodeDef]:
    return _REGISTRY.get(type)


def all_defs() -> List[NodeDef]:
    return list(_REGISTRY.values())


def load_all_nodes() -> None:
    """Import node modules so their @register decorators run."""
    from nodes import control, web, files, desktop  # noqa: F401
