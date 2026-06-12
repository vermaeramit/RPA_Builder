"""RPA Builder backend API (FastAPI).

Endpoints
---------
GET    /api/nodes               -> node-type catalog (drives the palette & forms)
GET    /api/workflows           -> list saved workflows
GET    /api/workflows/{id}      -> load one workflow
POST   /api/workflows           -> create/update a workflow
DELETE /api/workflows/{id}      -> delete a workflow
POST   /api/run                 -> run a workflow graph now, return logs
GET    /api/schedules           -> list schedules
POST   /api/schedules           -> schedule a saved workflow (cron)
DELETE /api/schedules/{job_id}  -> remove a schedule
GET    /api/runs                -> list recent run history
GET    /api/runs/{id}           -> one run's detail (full log + variables)
POST   /api/auth/login          -> exchange username/password for a JWT
GET    /api/auth/me             -> current user
GET    /api/users               -> list users (admin)
POST   /api/users               -> create user (admin)
PATCH  /api/users/{id}/role     -> change a user's role (admin)
DELETE /api/users/{id}          -> delete user (admin)

Access control (roles: viewer < editor < admin):
  viewer  - read endpoints (nodes, workflows, runs, schedules)
  editor  - + run flows, workflow CRUD, schedule CRUD
  admin   - + user management

Run endpoints are plain `def` so FastAPI runs them in a worker thread — this
lets Playwright's sync API work (it refuses to run inside an asyncio loop).
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import auth
import db
import runstore
import scheduler
import storage
from engine import executor, registry

registry.load_all_nodes()


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    db.init_db()           # create tables if missing
    auth.bootstrap_admin() # create default admin if no users exist
    scheduler.start()      # start APScheduler (reloads persisted schedules)
    yield
    scheduler.shutdown()


app = FastAPI(title="RPA Builder", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- models ---------------------------------------------------------------
class WorkflowIn(BaseModel):
    id: Optional[str] = None
    name: str = "Untitled"
    graph: Dict[str, Any] = {}


class RunIn(BaseModel):
    graph: Dict[str, Any]
    workflow_id: Optional[str] = None
    name: Optional[str] = None


class ScheduleIn(BaseModel):
    workflow_id: str
    cron: str


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class RoleIn(BaseModel):
    role: str


# ---- auth -----------------------------------------------------------------
@app.post("/api/auth/login")
def login(body: LoginIn) -> dict:
    user = auth.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Invalid username or password")
    token = auth.create_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.get_current_user)) -> dict:
    return user


# ---- users (admin only) ---------------------------------------------------
@app.get("/api/users")
def get_users(user: dict = Depends(auth.require_role("admin"))) -> List[dict]:
    return auth.list_users()


@app.post("/api/users")
def add_user(body: UserIn, user: dict = Depends(auth.require_role("admin"))) -> dict:
    if body.role == "superadmin" and not auth.is_superadmin(user):
        raise HTTPException(403, "Only a superadmin can grant the superadmin role")
    try:
        return auth.create_user(body.username, body.password, body.role)
    except ValueError as ex:
        raise HTTPException(400, str(ex))


@app.patch("/api/users/{user_id}/role")
def change_role(user_id: str, body: RoleIn, user: dict = Depends(auth.require_role("admin"))) -> dict:
    if body.role == "superadmin" and not auth.is_superadmin(user):
        raise HTTPException(403, "Only a superadmin can grant the superadmin role")
    target = auth.get_user_by_id(user_id)
    if target and target["role"] == "superadmin" and not auth.is_superadmin(user):
        raise HTTPException(403, "Only a superadmin can change a superadmin's role")
    try:
        updated = auth.set_role(user_id, body.role)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    if not updated:
        raise HTTPException(404, "User not found")
    return updated


@app.delete("/api/users/{user_id}")
def remove_user(user_id: str, user: dict = Depends(auth.require_role("admin"))) -> dict:
    if user["id"] == user_id:
        raise HTTPException(400, "You cannot delete your own account")
    target = auth.get_user_by_id(user_id)
    if target and target["role"] == "superadmin" and not auth.is_superadmin(user):
        raise HTTPException(403, "Only a superadmin can delete a superadmin")
    return {"deleted": auth.delete_user(user_id)}


# ---- node catalog ---------------------------------------------------------
@app.get("/api/nodes")
def get_nodes(user: dict = Depends(auth.require_role("viewer"))) -> List[dict]:
    return [d.to_dict() for d in registry.all_defs()]


# ---- workflows ------------------------------------------------------------
@app.get("/api/workflows")
def list_workflows(user: dict = Depends(auth.require_role("viewer"))) -> List[dict]:
    return storage.list_workflows(user["id"], auth.is_superadmin(user))


@app.get("/api/workflows/{wf_id}")
def get_workflow(wf_id: str, user: dict = Depends(auth.require_role("viewer"))) -> dict:
    wf = storage.get_workflow(wf_id, user["id"], auth.is_superadmin(user))
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


@app.post("/api/workflows")
def save_workflow(body: WorkflowIn, user: dict = Depends(auth.require_role("editor"))) -> dict:
    try:
        return storage.save_workflow(
            body.id, body.name, body.graph, user["id"], auth.is_superadmin(user)
        )
    except storage.AccessDenied as ex:
        raise HTTPException(403, str(ex))


@app.delete("/api/workflows/{wf_id}")
def delete_workflow(wf_id: str, user: dict = Depends(auth.require_role("editor"))) -> dict:
    try:
        return {"deleted": storage.delete_workflow(wf_id, user["id"], auth.is_superadmin(user))}
    except storage.AccessDenied as ex:
        raise HTTPException(403, str(ex))


# ---- run ------------------------------------------------------------------
@app.post("/api/run")
def run(body: RunIn, user: dict = Depends(auth.require_role("editor"))) -> dict:
    started = runstore.now()
    ctx = executor.run_workflow(body.graph)
    run_id = runstore.save_run(
        ctx, started=started, finished=runstore.now(),
        workflow_id=body.workflow_id, workflow_name=body.name, trigger="manual",
        owner_id=user["id"],
    )
    return {"run_id": run_id, "logs": ctx.logs, "variables": _safe_vars(ctx.vars)}


@app.websocket("/api/run/ws")
async def run_ws(ws: WebSocket) -> None:
    """Run a workflow and stream each log entry to the client as it happens.

    The workflow runs in a worker thread (Playwright's sync API can't run inside
    an asyncio loop). Log entries are bridged back to this coroutine through an
    asyncio.Queue via call_soon_threadsafe.

    Auth: pass the JWT as a `?token=` query param (WebSockets can't send the
    Authorization header from the browser). Requires the 'editor' role.
    """
    await ws.accept()
    token = ws.query_params.get("token", "")
    owner_id = None
    try:
        payload = auth._decode(token)
        role = payload.get("role", "")
        if auth.ROLES.get(role, 0) < auth.ROLES["editor"]:
            raise PermissionError
        u = auth.get_user(payload.get("sub"))
        owner_id = u.id if u else None
    except Exception:
        await ws.send_json({"type": "error", "message": "Unauthorized"})
        await ws.close(code=4401)
        return
    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return
    graph = data.get("graph", {})
    workflow_id = data.get("workflow_id")
    name = data.get("name")

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_log(entry: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "log", "entry": entry})

    def worker() -> None:
        started = runstore.now()
        ctx = executor.run_workflow(graph, on_log=on_log)
        run_id = runstore.save_run(
            ctx, started=started, finished=runstore.now(),
            workflow_id=workflow_id, workflow_name=name, trigger="manual",
            owner_id=owner_id,
        )
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "done", "run_id": run_id, "variables": _safe_vars(ctx.vars)},
        )

    threading.Thread(target=worker, daemon=True).start()

    try:
        while True:
            msg = await queue.get()
            await ws.send_json(msg)
            if msg.get("type") == "done":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()


def _safe_vars(vars: dict) -> dict:
    """Trim large/unserializable values so the response stays small."""
    out = {}
    for k, v in vars.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list):
            out[k] = f"<list: {len(v)} items>"
        else:
            out[k] = f"<{type(v).__name__}>"
    return out


# ---- schedules ------------------------------------------------------------
@app.get("/api/schedules")
def list_schedules(user: dict = Depends(auth.require_role("viewer"))) -> List[dict]:
    return scheduler.list_schedules(user["id"], auth.is_superadmin(user))


@app.post("/api/schedules")
def add_schedule(body: ScheduleIn, user: dict = Depends(auth.require_role("editor"))) -> dict:
    try:
        return scheduler.add_schedule(
            body.workflow_id, body.cron, user["id"], auth.is_superadmin(user)
        )
    except Exception as ex:
        raise HTTPException(400, str(ex))


@app.delete("/api/schedules/{job_id}")
def remove_schedule(job_id: str, user: dict = Depends(auth.require_role("editor"))) -> dict:
    return {"removed": scheduler.remove_schedule(job_id, user["id"], auth.is_superadmin(user))}


# ---- run history ----------------------------------------------------------
@app.get("/api/runs")
def list_runs(limit: int = 50, user: dict = Depends(auth.require_role("viewer"))) -> List[dict]:
    return runstore.list_runs(user["id"], auth.is_superadmin(user), limit)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, user: dict = Depends(auth.require_role("viewer"))) -> dict:
    r = runstore.get_run(run_id, user["id"], auth.is_superadmin(user))
    if not r:
        raise HTTPException(404, "Run not found")
    return r


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "nodes": len(registry.all_defs())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
