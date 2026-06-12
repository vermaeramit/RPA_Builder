"""Schedule saved workflows on a cron expression (APScheduler + Postgres).

Triggers are persisted in Postgres via APScheduler's SQLAlchemyJobStore, so
schedules survive a backend restart. We also keep a small `schedules` table with
display metadata (workflow name + the original cron string the user typed).

Weekday note: APScheduler's from_crontab() reads a numeric weekday as 0=Monday,
which disagrees with standard cron (0/7=Sunday, 1=Monday). We translate numeric
weekdays to day-name abbreviations, which APScheduler maps to the correct day.
"""
from __future__ import annotations

import re
import threading
from typing import List, Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

import auth
import runstore
import storage
from db import SessionLocal, engine
from engine import executor
from models import Schedule

_scheduler = BackgroundScheduler(jobstores={"default": SQLAlchemyJobStore(engine=engine)})
_lock = threading.Lock()

_DOW_NAMES = {0: "sun", 1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


def _normalize_cron(cron: str) -> str:
    parts = cron.split()
    if len(parts) == 5:
        parts[4] = re.sub(
            r"\d+", lambda m: _DOW_NAMES.get(int(m.group()), m.group()), parts[4]
        )
    return " ".join(parts)


def start() -> None:
    if not _scheduler.running:
        _scheduler.start()


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def _run_job(workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Executed by APScheduler when a schedule fires. Runs the flow and records history."""
    wf = storage.get_workflow(workflow_id, owner_id or "", see_all=True)
    if not wf:
        return
    started = runstore.now()
    ctx = executor.run_workflow(wf.get("graph", {}))
    runstore.save_run(
        ctx,
        started=started,
        finished=runstore.now(),
        workflow_id=workflow_id,
        workflow_name=wf.get("name"),
        trigger="schedule",
        owner_id=owner_id,
    )


def add_schedule(workflow_id: str, cron: str, owner_id: str, see_all: bool) -> dict:
    """cron is a 5-field expression: 'min hour day month day_of_week'."""
    wf = storage.get_workflow(workflow_id, owner_id, see_all=see_all)
    if not wf:
        raise ValueError("Workflow not found")

    trigger = CronTrigger.from_crontab(_normalize_cron(cron))
    with _lock:
        job = _scheduler.add_job(_run_job, trigger, args=[workflow_id, owner_id])
        with SessionLocal() as s:
            s.merge(Schedule(job_id=job.id, workflow_id=workflow_id,
                             name=wf.get("name"), cron=cron, owner_id=owner_id))
            s.commit()
    return {"job_id": job.id, "workflow_id": workflow_id, "name": wf.get("name"),
            "cron": cron, "owner_id": owner_id}


def list_schedules(viewer_id: str, see_all: bool) -> List[dict]:
    names = auth.username_map()
    with SessionLocal() as s:
        q = select(Schedule)
        if not see_all:
            q = q.where(Schedule.owner_id == viewer_id)
        rows = s.execute(q).scalars().all()
        out = []
        for sc in rows:
            job = _scheduler.get_job(sc.job_id)
            nxt = str(job.next_run_time) if job and job.next_run_time else None
            out.append(
                {
                    "job_id": sc.job_id,
                    "workflow_id": sc.workflow_id,
                    "name": sc.name,
                    "cron": sc.cron,
                    "next_run": nxt,
                    "owner_id": sc.owner_id,
                    "owner": names.get(sc.owner_id, "—"),
                }
            )
        return out


def remove_schedule(job_id: str, viewer_id: str, see_all: bool) -> bool:
    with _lock:
        with SessionLocal() as s:
            sc = s.get(Schedule, job_id)
            if not sc:
                return False
            if not see_all and sc.owner_id != viewer_id:
                return False
            try:
                _scheduler.remove_job(job_id)
            except Exception:
                pass
            s.delete(sc)
            s.commit()
            return True
