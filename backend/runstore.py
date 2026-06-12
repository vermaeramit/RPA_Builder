"""Run history persistence (Postgres), owner-scoped.

Each run records the owner who triggered it (or the schedule's owner). Listing
and detail are scoped to the owner unless the caller is a superadmin.
"""
from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import select

import auth
from db import SessionLocal
from engine.context import RunContext
from models import Run


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _safe_vars(vars: dict) -> dict:
    """Trim large/unserializable values so the stored row stays small & JSON-safe."""
    out = {}
    for k, v in vars.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list):
            out[k] = f"<list: {len(v)} items>"
        else:
            out[k] = f"<{type(v).__name__}>"
    return out


def save_run(
    ctx: RunContext,
    started: datetime.datetime,
    finished: datetime.datetime,
    workflow_id: Optional[str] = None,
    workflow_name: Optional[str] = None,
    trigger: str = "manual",
    owner_id: Optional[str] = None,
) -> str:
    status = "failed" if any(l.get("level") == "error" for l in ctx.logs) else "success"
    duration_ms = int((finished - started).total_seconds() * 1000)
    run_id = ctx.run_id or uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        s.merge(
            Run(
                id=run_id,
                workflow_id=workflow_id,
                workflow_name=workflow_name or "Ad-hoc run",
                status=status,
                trigger=trigger,
                started=started,
                finished=finished,
                duration_ms=duration_ms,
                logs=ctx.logs,
                variables=_safe_vars(ctx.vars),
                owner_id=owner_id,
            )
        )
        s.commit()
    return run_id


def list_runs(viewer_id: str, see_all: bool, limit: int = 50) -> List[dict]:
    names = auth.username_map()
    with SessionLocal() as s:
        q = select(Run).order_by(Run.started.desc()).limit(limit)
        if not see_all:
            q = q.where(Run.owner_id == viewer_id)
        rows = s.execute(q).scalars().all()
        return [
            {
                "id": r.id,
                "workflow_id": r.workflow_id,
                "workflow_name": r.workflow_name,
                "status": r.status,
                "trigger": r.trigger,
                "started": r.started.isoformat() if r.started else None,
                "duration_ms": r.duration_ms,
                "owner_id": r.owner_id,
                "owner": names.get(r.owner_id, "—"),
            }
            for r in rows
        ]


def get_run(run_id: str, viewer_id: str, see_all: bool) -> Optional[dict]:
    with SessionLocal() as s:
        r = s.get(Run, run_id)
        if not r:
            return None
        if not see_all and r.owner_id != viewer_id:
            return None
        return {
            "id": r.id,
            "workflow_id": r.workflow_id,
            "workflow_name": r.workflow_name,
            "status": r.status,
            "trigger": r.trigger,
            "started": r.started.isoformat() if r.started else None,
            "finished": r.finished.isoformat() if r.finished else None,
            "duration_ms": r.duration_ms,
            "logs": r.logs or [],
            "variables": r.variables or {},
            "owner_id": r.owner_id,
            "owner": auth.username_map().get(r.owner_id, "—"),
        }
