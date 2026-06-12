"""Workflow persistence (Postgres via SQLAlchemy), owner-scoped.

Non-superadmin callers only see/modify workflows they own (`owner_id`).
Superadmin callers (`see_all=True`) see everything.
"""
from __future__ import annotations

import time
import uuid
from typing import List, Optional

from sqlalchemy import select

import auth
from db import SessionLocal
from models import Workflow


class AccessDenied(Exception):
    pass


def _to_dict(wf: Workflow, names: Optional[dict] = None) -> dict:
    names = names if names is not None else auth.username_map()
    return {
        "id": wf.id,
        "name": wf.name,
        "graph": wf.graph or {},
        "updated": wf.updated,
        "owner_id": wf.owner_id,
        "owner": names.get(wf.owner_id, "—"),
    }


def list_workflows(viewer_id: str, see_all: bool) -> List[dict]:
    names = auth.username_map()
    with SessionLocal() as s:
        q = select(Workflow).order_by(Workflow.updated.desc())
        if not see_all:
            q = q.where(Workflow.owner_id == viewer_id)
        rows = s.execute(q).scalars().all()
        return [
            {"id": w.id, "name": w.name, "updated": w.updated,
             "owner_id": w.owner_id, "owner": names.get(w.owner_id, "—")}
            for w in rows
        ]


def get_workflow(wf_id: str, viewer_id: str, see_all: bool) -> Optional[dict]:
    with SessionLocal() as s:
        wf = s.get(Workflow, wf_id)
        if not wf:
            return None
        if not see_all and wf.owner_id != viewer_id:
            return None  # hide existence of others' workflows
        return _to_dict(wf)


def save_workflow(
    wf_id: Optional[str], name: str, graph: dict, owner_id: str, see_all: bool
) -> dict:
    with SessionLocal() as s:
        wf = s.get(Workflow, wf_id) if wf_id else None
        if wf is None:
            wf = Workflow(id=wf_id or uuid.uuid4().hex[:8], owner_id=owner_id)
            s.add(wf)
        else:
            # Updating an existing workflow — must own it (unless superadmin).
            if not see_all and wf.owner_id != owner_id:
                raise AccessDenied("You can only edit your own workflows")
            if wf.owner_id is None:
                wf.owner_id = owner_id
        wf.name = name
        wf.graph = graph
        wf.updated = int(time.time())
        s.commit()
        return _to_dict(wf)


def delete_workflow(wf_id: str, viewer_id: str, see_all: bool) -> bool:
    with SessionLocal() as s:
        wf = s.get(Workflow, wf_id)
        if not wf:
            return False
        if not see_all and wf.owner_id != viewer_id:
            raise AccessDenied("You can only delete your own workflows")
        s.delete(wf)
        s.commit()
        return True
