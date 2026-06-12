# Deploying RPA Builder with Docker

This stack runs two containers on their own bridge network and publishes **only**
the web UI on a single host port (default `3000`). The backend is internal. It
connects to your existing PostgreSQL — nothing else on the host is touched.

```
            host:3000
               │
        ┌──────▼───────┐        ┌──────────────┐        ┌────────────────────┐
        │  web (nginx) │ ─/api─▶ │   backend    │ ─────▶ │ Postgres           │
        │  React app   │  proxy │ FastAPI+PW    │        │ 10.130.9.249:5432  │
        └──────────────┘        └──────────────┘        └────────────────────┘
              rpa-net (isolated bridge network)
```

## Prerequisites on the server (Ubuntu 10.130.9.241)

- Docker Engine + Compose plugin (`docker --version`, `docker compose version`)
- Outbound access to `10.130.9.249:5432` (the Postgres host)
- A free host port (default **3000** — change `WEB_PORT` if taken)

## First-time deploy

```bash
# 1. Clone (private repo)
git clone https://github.com/vermaeramit/RPA_Builder.git
cd RPA_Builder

# 2. Create the env file from the template and fill in real values
cp .env.example .env
nano .env
#   - DATABASE_URL  -> your Postgres (URL-encode '@' in the password as %40)
#   - JWT_SECRET    -> openssl rand -hex 32
#   - ADMIN_PASSWORD-> a strong password
#   - WEB_PORT      -> 3000 (or another free port)

# 3. Build and start (detached)
docker compose up -d --build

# 4. Check status / logs
docker compose ps
docker compose logs -f backend     # watch for "Application startup complete"
```

Open **http://10.130.9.241:3000** and sign in with the `ADMIN_USERNAME` /
`ADMIN_PASSWORD` you set (role: superadmin). **Change the password** immediately
via the 👥 Users panel.

## Updating after new commits

```bash
cd RPA_Builder
git pull
docker compose up -d --build
```

## Common operations

```bash
docker compose down            # stop & remove the two containers (keeps DB — it's external)
docker compose restart backend # restart just the API
docker compose logs -f web     # nginx access/error logs
```

## Deploying via Portainer (alternative)

Portainer → **Stacks → Add stack** → *Repository* → point at this repo, set
**Compose path** to `docker-compose.yml`, add the env vars from `.env.example`
as stack environment variables, and deploy.

## Notes

- **Ports:** only `WEB_PORT` (3000) is published. The backend (8000 inside the
  network) is not exposed to the host, so it can't clash with your other apps.
- **Scheduler:** the backend runs a single uvicorn worker on purpose — multiple
  workers would each run the scheduler and fire schedules more than once.
- **Browser automation:** Chromium is included in the backend image and runs
  against a virtual display (Xvfb), so Web nodes work headless or not.
- **Desktop automation** (mouse/keyboard nodes) is **not** supported in a
  container — there's no real desktop session. Use Web / Files / HTTP nodes on
  the server.
- **Secrets:** `.env` is gitignored and must be created on the server; never
  commit real credentials.
