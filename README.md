# RPA Builder

A visual, drag-and-drop **Robotic Process Automation** builder. Wire together
steps on a canvas to automate the web, desktop apps, files/data, and run flows
on a schedule.

```
┌────────────┐   drag/drop   ┌──────────────────────────┐   REST    ┌──────────────────┐
│  Palette   │ ────────────▶ │  React Flow canvas (UI)   │ ◀───────▶ │  FastAPI engine   │
│ (steps)    │               │  build • save • run flows │           │  runs each node   │
└────────────┘               └──────────────────────────┘           └──────────────────┘
```

- **Frontend:** React + [React Flow](https://reactflow.dev) — the node canvas, palette, and properties panel.
- **Backend:** Python + FastAPI — a node registry + graph executor.
- **Database:** PostgreSQL via SQLAlchemy — stores workflows, run history, and schedules.

### Data model (Postgres)

| Table | Holds |
|---|---|
| `workflows` | Saved flow graphs (`{nodes, edges}` as JSONB) |
| `runs` | Run history: status, trigger, timing, full log, final variables |
| `schedules` | Schedule metadata (workflow + original cron string) |
| `apscheduler_jobs` | APScheduler's persisted triggers (auto-managed) |

## Step library

| Category | Steps |
|---|---|
| **Control** | Start, Log Message, Wait/Delay, Set Variable, If/Condition (branching), Loop (For Each) |
| **Web** | Open Browser, Go to URL, Click, Type Text, Extract Text, Screenshot, Close Browser (Playwright) |
| **Files & Data** | Read CSV/Excel, Write CSV/Excel, Write Text File, HTTP Request |
| **Desktop** | Launch Application, Type Keys, Press Hotkey, Click at Position (pyautogui) |

Add a new step by writing one `@register(...)` function in `backend/nodes/` —
the palette and the properties form update automatically from the registry.

## Variables & templating

Steps can store values in variables (e.g. *Extract Text → `title`*, *Set Variable*,
*HTTP Request*). Any text field supports `{{variable}}` templating, so a later
step can reference `{{title}}`.

## Setup

### 1. Database

Point the backend at a PostgreSQL database via a `.env` file:

```powershell
cd d:\RND\RPA_Builder\backend
copy .env.example .env
# edit .env -> DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

- If the password contains special characters, URL-encode them (e.g. `@` → `%40`).
- The database itself must exist; tables are created automatically on first boot.
  To create the database:
  `CREATE DATABASE "RPA_Builder";`

### 2. Backend

```powershell
cd d:\RND\RPA_Builder\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium   # one-time, for web automation
python main.py                          # serves http://127.0.0.1:8000
```

### 2. Frontend

```powershell
cd d:\RND\RPA_Builder\frontend
npm install
npm run dev                             # serves http://127.0.0.1:5173
```

Open **http://127.0.0.1:5173**. The Vite dev server proxies `/api/*` to the backend.

## Build your first flow

1. Drag **Start** onto the canvas.
2. Drag **Open Browser**, **Go to URL**, **Extract Text**, **Log Message**.
3. Connect them by dragging from the bottom handle of one node to the top handle of the next.
4. Click a node to set its parameters (e.g. URL = `example.com`, selector = `h1`, store in `title`).
5. Set the Log step's message to `Title is {{title}}`.
6. Press **▶ Run** and watch the log panel.
7. **Save** the flow, then schedule it via the API (see below).

## Scheduling

Open the **🕘 Schedules** panel in the toolbar to schedule any saved workflow on
a cron expression (5-field: `min hour day month dow`), with presets for common
cadences. Schedules are **persisted in Postgres** and reloaded automatically when
the backend restarts.

Standard cron weekday numbering is used (`0`/`7` = Sunday, `1` = Monday). You can
also use the REST API directly:

```powershell
# every Monday at 9am, run workflow <id>
curl -X POST http://127.0.0.1:8000/api/schedules -H "Content-Type: application/json" `
  -d '{"workflow_id":"<id>","cron":"0 9 * * 1"}'
```

## Authentication & roles (RBAC)

The app requires sign-in. Auth is JWT-based; every API call carries a bearer
token, and each endpoint enforces a minimum role.

| Role | Can do | Data scope |
|---|---|---|
| **viewer** | Read-only: browse workflows, run history, schedules | own only |
| **editor** | viewer **+** run flows, create/edit/delete workflows, manage schedules | own only |
| **admin** | editor **+** manage users (cannot grant/modify superadmin) | own only |
| **superadmin** | admin **+** see & manage **all users'** workflows, runs, logs, schedules | everything |

**Data ownership.** Every workflow, run, and schedule has an `owner_id`. All
non-superadmin roles — including admin — only see and act on rows they own.
A **superadmin** sees everything across all users, with the owner shown in the
Open dropdown, History, and Schedules panels. Accessing another user's resource
by id returns 404 (existence is hidden); modifying it returns 403.

- On first startup, if the `users` table is empty, a **bootstrap superadmin** is
  created from `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env` (default `admin` / `admin`).
  **Change this immediately** via the **👥 Users** panel.
- Set a long, random `JWT_SECRET` in `.env` for any real deployment. Tokens expire
  after `JWT_EXPIRE_HOURS` (default 12).
- The UI hides actions a role can't perform; the server enforces it regardless
  (the UI gate is convenience, the API check is the real boundary).

Endpoints: `POST /api/auth/login`, `GET /api/auth/me`, and admin-only
`GET/POST /api/users`, `PATCH /api/users/{id}/role`, `DELETE /api/users/{id}`.

## Run history

Every run — manual or scheduled — is recorded in Postgres with its status,
duration, full log, and final variables. Open the **📜 History** panel in the
toolbar to browse past runs and inspect any run's log. API: `GET /api/runs`,
`GET /api/runs/{id}`.

## Loops

The **Loop (For Each)** step iterates a list variable (e.g. `rows` from *Read
CSV/Excel*). Wire its **body** output to the steps you want to repeat, then
connect the **last** body step back to the Loop node. Inside the body, reference
the current element as `{{item}}` and its position as `{{item_index}}`. When the
list is exhausted, the **done** output fires.

```
Read CSV ──▶ Loop ──body──▶ [do something with {{item}}] ──┐
                 │                                          │
                 └──◀──────────── (loop back) ─────────────┘
                 │
                 done ──▶ Finish
```

## Live run log

The **▶ Run** button streams log lines over a WebSocket (`/api/run/ws`) so the
Run panel updates in real time as each step executes. If the socket can't
connect, the UI falls back to the one-shot `POST /api/run` endpoint.

## Notes / next steps

- Desktop steps drive the real mouse/keyboard — they need an interactive session.
- Add new steps by writing one `@register(...)` function in `backend/nodes/`.
- `.env` holds the DB credentials and is gitignored — never commit it.
- For schema migrations beyond auto-create, add Alembic.
