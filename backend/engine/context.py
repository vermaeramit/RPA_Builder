"""Execution context shared across all nodes in a single run.

Holds workflow variables, a structured log, and a place to stash shared
resources (like an open browser) that nodes create and later nodes reuse.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

_TEMPLATE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


class RunContext:
    def __init__(self, run_id: str, on_log: Optional[Callable[[dict], None]] = None):
        self.run_id = run_id
        self.vars: Dict[str, Any] = {}
        self.resources: Dict[str, Any] = {}   # e.g. {"page": <playwright page>}
        self.node_state: Dict[str, Any] = {}  # per-node persistent state (e.g. loop index)
        self.logs: List[dict] = []
        self._on_log = on_log
        self.cancelled = False

    def log(self, message: str, level: str = "info", node_id: str = "") -> None:
        entry = {
            "ts": time.strftime("%H:%M:%S"),
            "level": level,
            "node_id": node_id,
            "message": str(message),
        }
        self.logs.append(entry)
        if self._on_log:
            try:
                self._on_log(entry)
            except Exception:
                pass

    def render(self, value: Any) -> Any:
        """Substitute {{var}} references in strings using current variables."""
        if not isinstance(value, str):
            return value

        def repl(m: "re.Match") -> str:
            key = m.group(1).strip()
            return str(self.vars.get(key, m.group(0)))

        return _TEMPLATE.sub(repl, value)

    def render_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self.render(v) for k, v in params.items()}

    def cleanup(self) -> None:
        """Release any shared resources (close browser, etc.)."""
        browser = self.resources.pop("browser", None)
        pw = self.resources.pop("playwright", None)
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass
