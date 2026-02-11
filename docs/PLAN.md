# cronbox: Job Scheduler & Runner

## Context

Replace ad-hoc crontab + shell scripts with a proper job scheduler that runs all jobs in Docker containers, captures logs, tracks success/failure, sends Discord alerts on failure, and provides a web UI dashboard. The user's current setup has 3 market-data jobs running on weekdays via crontab, using `docker start` + `docker exec` on a persistent `polygon_rip` container.

## Stack

- **Backend**: Python 3.12+ — FastAPI (API + static file serving), APScheduler 4.x (scheduling), Docker SDK (container ops), SQLAlchemy + aiosqlite (run history + user/auth data), httpx (Discord webhooks), PyJWT (authentication tokens), bcrypt (password hashing)
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4 + TanStack Query
- **Config**: YAML files in `config/jobs/` (one per job)
- **Storage**: SQLite for run metadata + users + API keys, disk files for logs
- **Auth**: JWT access/refresh tokens for browser sessions, per-user API keys for programmatic access, 3-role RBAC (admin/operator/viewer)

## Project Structure

```
cronbox/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── docs/
│   ├── PLAN.md                      # This file
│   └── THINKING_LOG.md              # Decision log
├── config/jobs/                     # YAML job definitions
│   ├── polygon_sync.yml
│   ├── etf_holdings.yml
│   └── vix_stuff.yml
├── src/cronbox/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + lifespan
│   ├── config.py                    # Settings (env-configurable via CRONBOX_ prefix)
│   ├── cli.py                       # CLI: `cronbox create-user`, `cronbox serve`
│   ├── utils.py                     # Shared utilities (read_log_tail)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job_config.py            # Pydantic models for YAML schema
│   │   ├── database.py              # SQLAlchemy models (job_runs, step_results)
│   │   ├── auth.py                  # Auth models (users, api_keys, refresh_tokens)
│   │   ├── queries.py               # Shared query helpers (batch latest runs)
│   │   └── api_models.py            # API response schemas
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── engine.py                # APScheduler lifecycle + schedule registration
│   │   └── loader.py                # YAML file loading + validation
│   ├── executor/
│   │   ├── __init__.py
│   │   ├── runner.py                # Job execution orchestrator
│   │   ├── docker_ops.py            # Docker SDK (start/exec/run)
│   │   └── log_capture.py           # Log file creation + writing
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── discord.py               # Discord webhook on failure
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py                # FastMCP server: tools + resources
│   │   └── __main__.py              # `python -m cronbox.mcp` entrypoint
│   └── api/
│       ├── __init__.py
│       ├── auth.py                  # Auth dependency (JWT + API key verification)
│       ├── permissions.py           # RBAC dependency factories (require_admin, etc.)
│       ├── routes_auth.py           # /api/auth — login, refresh, logout, me
│       ├── routes_keys.py           # /api/keys — API key CRUD
│       ├── routes_users.py          # /api/admin/users — user management (admin-only)
│       ├── routes_jobs.py           # /api/jobs — list, detail, trigger, reload
│       ├── routes_runs.py           # /api/runs — run history + detail
│       └── routes_logs.py           # /api/logs — log file listing + content
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx                  # Entry: AuthProvider + QueryClient + Router
│       ├── App.tsx                   # Router with protected routes
│       ├── api.ts                    # Fetch wrapper with auth headers + 401 handling
│       ├── types.ts                  # TypeScript types mirroring API models
│       ├── context/
│       │   └── AuthContext.tsx       # Auth state: login, logout, token refresh
│       └── components/
│           ├── Layout.tsx            # Shell with header + nav + user menu
│           ├── Login.tsx             # Login page (username/password)
│           ├── ProtectedRoute.tsx    # Auth gate wrapper
│           ├── Settings.tsx          # User profile + API key management
│           ├── AdminUsers.tsx        # Admin user management (admin-only)
│           ├── JobList.tsx           # Dashboard table with status badges
│           ├── JobDetail.tsx         # Config + run history + trigger button
│           ├── LogViewer.tsx         # Monospace log viewer with follow mode
│           └── StatusBadge.tsx       # Green/red/blue/gray status indicators
├── logs/                             # Runtime (git-ignored): per-job timestamped log files
└── data/                             # Runtime (git-ignored): SQLite database
```

## YAML Job Config Schema

Each job is a single YAML file in `config/jobs/`.

```yaml
name: polygon_sync
description: "Daily polygon data sync"

schedule:
  cron: "0 4 * * 2-6"               # Standard 5-field cron expression
  timezone: "America/New_York"
  enabled: true

container:
  mode: persistent                    # persistent (start+exec) or ephemeral (run)
  name: polygon_rip                   # For persistent mode
  # image: "myimage:latest"          # For ephemeral mode
  # volumes: {"/host/path": "/container/path"}
  # network: "bridge"

steps:
  - name: sync_data
    command: "/polygon/sync.sh"
    timeout_seconds: 3600
    # workdir: "/app"
    # environment: {KEY: "value"}
    # user: "appuser"

notify:
  on_failure: true
  on_success: false
  # discord_webhook_url: "override_url"  # Per-job override of global webhook

timeout_seconds: 7200                 # Overall job timeout
```

### Container Modes

- **persistent**: Uses `docker start` + `docker exec` on a named, already-existing container. Maps to the user's current `polygon_rip` pattern.
- **ephemeral**: Uses `docker run --rm` with a fresh container each time. Useful for isolated one-off jobs.

### Step Execution

Jobs support multiple sequential steps. If any step fails (non-zero exit code), remaining steps are skipped and the job is marked failed.

## Concrete Job Configs (from existing crontab)

### polygon_sync.yml
```yaml
name: polygon_sync
description: "Daily polygon data sync (Tue-Sat at 4:00 AM ET)"
schedule:
  cron: "0 4 * * 2-6"
  timezone: "America/New_York"
container:
  mode: persistent
  name: polygon_rip
steps:
  - name: sync_data
    command: "/polygon/sync.sh"
    timeout_seconds: 3600
notify:
  on_failure: true
```

### etf_holdings.yml
```yaml
name: etf_holdings
description: "ETF holdings update (Tue-Sat at 8:00 AM ET)"
schedule:
  cron: "0 8 * * 2-6"
  timezone: "America/New_York"
container:
  mode: persistent
  name: polygon_rip
steps:
  - name: fetch_holdings
    command: "python /etf_holdings/fetch_vixy_holdings.py"
    timeout_seconds: 1800
notify:
  on_failure: true
```

### vix_stuff.yml
```yaml
name: vix_stuff
description: "VIX regime + curvature analysis (Mon-Fri at 11:30 PM ET)"
schedule:
  cron: "30 23 * * 1-5"
  timezone: "America/New_York"
container:
  mode: persistent
  name: polygon_rip
steps:
  - name: regime_analysis
    command: "python /regime.py"
    timeout_seconds: 1800
  - name: curvature_analysis
    command: "python /curvature.py"
    timeout_seconds: 1800
notify:
  on_failure: true
```

## Execution Flow

```
APScheduler fires → execute_job(config)
  → Create JobRun record in SQLite (status=running)
  → Open log file: logs/{job_name}/{timestamp}.log
  → For each step:
      → [persistent] docker_ops.ensure_started() + docker_ops.exec_in_container()
      → [ephemeral]  docker_ops.run_ephemeral_container()
      → Capture stdout/stderr → write to log file
      → Record StepResult in SQLite
      → If exit_code != 0 → abort remaining steps, mark job failed
  → Update JobRun (status=success|failed, duration)
  → If failed → send Discord webhook notification
  → Close log file
```

Docker operations are blocking I/O, run in thread pool via `asyncio.to_thread()`. Timeouts enforced at two levels:
- **Per-step**: `asyncio.wait_for(step_coro, timeout=step.timeout_seconds)`
- **Per-job**: `asyncio.wait_for(job_coro, timeout=job.timeout_seconds)`

## Authentication & Authorization

### Overview

Multi-user auth with three mechanisms:
1. **JWT tokens** — for browser sessions (login page → access token in localStorage + refresh token in httpOnly cookie)
2. **Per-user API keys** — for programmatic/MCP access (`cb_` prefixed, SHA-256 hashed, 30-day default expiry)
3. **Legacy API key** — backwards-compatible single shared key via `CRONBOX_API_KEY` env var

### Roles

| Role | Read (jobs/runs/logs) | Trigger jobs | Reload config | Manage users |
|------|----------------------|-------------|---------------|-------------|
| **viewer** | Yes | No | No | No |
| **operator** | Yes | Yes | No | No |
| **admin** | Yes | Yes | Yes | Yes |

### Auth Flow

- **Browser**: Login with username/password → JWT access token (15min) stored in localStorage, refresh token (7 days) as httpOnly cookie. Frontend auto-refreshes on 401.
- **API/MCP**: Include `X-API-Key: cb_...` header or `Authorization: Bearer cb_...` with a per-user API key.
- **Dev mode**: When `CRONBOX_JWT_SECRET` is empty and `CRONBOX_API_KEY` is empty, no auth required (local development).

### API Key Format

Keys use `cb_` prefix + 32 bytes of `secrets.token_urlsafe()`. Only the SHA-256 hash is stored. The full key is returned exactly once on creation. Display format shows only the prefix (e.g., `cb_xK7m2p9R...`).

### Bootstrap

First admin user is created via CLI:
```bash
cronbox create-user --username admin --email admin@example.com --role admin
```

## API Endpoints

All routes prefixed with `/api`. Frontend served at `/` as static files. All endpoints except `/api/auth/*` require authentication.

### Auth Endpoints (unauthenticated)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Username/password login → JWT tokens |
| POST | `/api/auth/refresh` | Refresh access token via refresh cookie/body |
| POST | `/api/auth/logout` | Revoke refresh token, clear cookie |
| GET | `/api/auth/me` | Current user info (requires auth) |

### Job Endpoints

| Method | Path | Role Required | Description |
|--------|------|--------------|-------------|
| GET | `/api/jobs` | viewer+ | List all jobs with next run time + last status |
| GET | `/api/jobs/{name}` | viewer+ | Job detail + step list + recent runs |
| POST | `/api/jobs/{name}/trigger` | operator+ | Trigger immediate manual run |
| POST | `/api/config/reload` | admin | Hot-reload YAML configs into scheduler |

### Run & Log Endpoints

| Method | Path | Role Required | Description |
|--------|------|--------------|-------------|
| GET | `/api/runs` | viewer+ | List recent runs across all jobs (paginated) |
| GET | `/api/runs?job_name=X` | viewer+ | Filter runs by job name |
| GET | `/api/runs/{id}` | viewer+ | Run detail with step results |
| GET | `/api/logs/{job_name}` | viewer+ | List log files for a job |
| GET | `/api/logs/{job_name}/{filename}` | viewer+ | Get log file contents (plain text) |

### API Key Endpoints

| Method | Path | Role Required | Description |
|--------|------|--------------|-------------|
| GET | `/api/keys` | viewer+ | List current user's API keys (prefix only) |
| POST | `/api/keys` | viewer+ | Generate new API key (returns full key once) |
| DELETE | `/api/keys/{id}` | viewer+ | Revoke an API key (owner or admin) |

### Admin Endpoints

| Method | Path | Role Required | Description |
|--------|------|--------------|-------------|
| GET | `/api/admin/users` | admin | List all users |
| POST | `/api/admin/users` | admin | Create new user |
| PUT | `/api/admin/users/{id}` | admin | Update user role/status |
| DELETE | `/api/admin/users/{id}` | admin | Deactivate user |

## MCP Server (FastMCP)

Exposes cronbox status and control to LLMs via MCP. Read-only for configs, plus job triggering. No config mutation — YAML files remain the sole source of truth, edited by humans.

### Transports

- **STDIO** (default): `python -m cronbox.mcp` — for Claude Desktop / Claude Code
- **HTTP**: `python -m cronbox.mcp --transport http --port 9100` — for remote LLM access

### Tools (read + trigger only)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `list_jobs` | — | All jobs with schedule, next run, last status |
| `get_job` | `job_name: str` | Job config + last 10 runs |
| `trigger_job` | `job_name: str` | Trigger immediate manual run, returns run_id |
| `list_runs` | `job_name?: str, limit: int = 20` | Recent runs, optionally filtered |
| `get_run` | `run_id: int` | Run detail with per-step results |
| `get_log` | `job_name: str, run_id?: int` | Log content (latest if run_id omitted) |
| `reload_config` | — | Hot-reload YAML configs |

No create/update/delete job tools — config changes are made by editing YAML files directly.

### Resources

| URI | Description |
|-----|-------------|
| `cronbox://jobs` | All job configs as JSON |
| `cronbox://jobs/{name}` | Single job config as YAML |
| `cronbox://status` | System status: uptime, total jobs, running, recent failures |

### Files

- `src/cronbox/mcp/server.py` — FastMCP server with `@mcp.tool` and `@mcp.resource` decorators
- `src/cronbox/mcp/__main__.py` — CLI entrypoint with `--transport` and `--port` args

Reuses internal modules directly: `scheduler/loader.py`, `models/database.py`, `executor/runner.py`, `scheduler/engine.py`, `config.py`. Operates standalone (no dependency on FastAPI running).

### MCP Authentication

The MCP server authenticates via `CRONBOX_MCP_API_KEY`. At startup, the lifespan resolves this key against the `api_keys` table to determine the user and their role. Mutating tools (`trigger_job`, `reload_config`) enforce RBAC based on the resolved user's role. If no key is configured and no `jwt_secret` is set, the MCP server operates in dev mode (no auth).

## Frontend

Single-page React app with auth-protected views. Dark theme (gray-950/900/800 backgrounds, gray-100 text).

### Login (`/login`)
- Full-page login form: username + password fields
- On success, stores JWT access token in localStorage, redirects to dashboard
- Refresh token handled via httpOnly cookie (transparent to frontend)

### Dashboard (`/`)
- Table of all jobs: Name, Schedule (human-readable), Next Run, Last Status, Last Run Time, Actions (trigger button)
- Status badges: green=success, red=failed, gray=never run, blue spinner=running
- Auto-polls `GET /api/jobs` every 10 seconds
- Trigger button visible only to operator+ roles

### Job Detail (`/jobs/:name`)
- Header: job name, description, cron schedule
- "Trigger Now" button → `POST /api/jobs/{name}/trigger` (operator+ only)
- Steps list: step name + command
- Run history table (last 50): Status, Started, Duration, Trigger type
- Each run row expands/links to show step results + log

### Settings (`/settings`)
- **Profile section**: username, email, role (read-only)
- **API Keys section**: table of user's keys (prefix, name, expiration, last used), generate new key (returns full key once with copy-to-clipboard), revoke button per key

### Admin Users (`/admin/users`) — admin only
- Table of all users: username, email, role, active status, created date
- Create new user, change role, deactivate/reactivate accounts

### Log Viewer (within job detail)
- Fetches log content as plain text
- Monospace, dark-themed scrollable container
- Highlights `[STDOUT]`, `[STDERR]`, exit codes, failure markers
- Auto-scrolls to bottom, "follow" toggle for in-progress runs (re-fetches every 3s)

### Auth Integration
- `AuthContext` manages user state, login/logout, token refresh
- `ProtectedRoute` wrapper redirects to `/login` if unauthenticated
- `api.ts` injects `Authorization: Bearer <token>` on all requests, auto-refreshes on 401
- Layout header shows username, Settings link, Admin link (admin only), Logout button

## Configuration

All settings via environment variables prefixed with `CRONBOX_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRONBOX_JOBS_CONFIG_DIR` | `config/jobs` | Path to YAML job files |
| `CRONBOX_LOGS_DIR` | `logs` | Path to log file directory |
| `CRONBOX_DB_PATH` | `data/cronbox.db` | SQLite database path |
| `CRONBOX_DISCORD_WEBHOOK_URL` | (empty) | Global Discord webhook URL |
| `CRONBOX_WEB_BASE_URL` | (empty) | Base URL for links in notifications |
| `CRONBOX_API_KEY` | (empty) | Legacy shared API key (deprecated, use JWT) |
| `CRONBOX_JWT_SECRET` | (empty) | JWT signing secret (required for multi-user auth) |
| `CRONBOX_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifetime |
| `CRONBOX_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `CRONBOX_API_KEY_DEFAULT_EXPIRE_DAYS` | `30` | Default API key expiration |
| `CRONBOX_MCP_API_KEY` | (empty) | API key for MCP server authentication |
| `CRONBOX_API_HOST` | `127.0.0.1` | API listen host |
| `CRONBOX_API_PORT` | `8000` | API listen port |
| `CRONBOX_LOG_RETENTION_DAYS` | `30` | Auto-delete logs older than this |

### Auth Behavior by Configuration

| `JWT_SECRET` | `API_KEY` | Behavior |
|---|---|---|
| empty | empty | No auth required (local dev mode) |
| empty | set | Legacy single shared key (backwards compat) |
| set | empty | Full multi-user JWT + per-user API keys |
| set | set | Multi-user auth + legacy key also accepted |

## Deployment

### Docker Compose (recommended)

```yaml
services:
  cronbox:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # Docker socket access
      - ./logs:/app/logs                            # Persist logs
      - ./data:/app/data                            # Persist SQLite
      - ./config:/app/config:ro                     # Job configs (editable without rebuild)
    environment:
      - CRONBOX_JWT_SECRET=${JWT_SECRET}
      - CRONBOX_DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
      - CRONBOX_WEB_BASE_URL=${WEB_BASE_URL:-http://localhost:8000}
    restart: unless-stopped
```

### Direct on host

```bash
pip install -e .
cronbox create-user --username admin --email admin@example.com --role admin
CRONBOX_JWT_SECRET=your-secret-here cronbox serve
```

Or with uvicorn directly:
```bash
CRONBOX_JWT_SECRET=your-secret-here uvicorn cronbox.main:app --host 127.0.0.1 --port 8000
```

Both modes work — Docker SDK uses `/var/run/docker.sock` either directly on host or via socket mount.

### CLI Commands

```bash
cronbox create-user --username NAME --email EMAIL --role admin|operator|viewer
cronbox serve [--host HOST] [--port PORT]
```

## Build Phases

All phases completed 2026-02-11.

1. **Phase 1 — Core engine** ✅: config.py, job_config.py, loader.py, docker_ops.py, log_capture.py, runner.py, engine.py, YAML job files.

2. **Phase 2 — Persistence + API** ✅: database.py, api_models.py, route files, main.py. Runner writes to SQLite.

3. **Phase 3 — Notifications** ✅: discord.py, wired into runner failure path.

4. **Phase 4 — MCP server** ✅: mcp/server.py (FastMCP tools + resources), mcp/__main__.py (CLI entrypoint). STDIO and HTTP transports.

5. **Phase 5 — Frontend** ✅: Vite + React 18 + TypeScript + Tailwind CSS v4 + TanStack Query. Components: JobList, JobDetail, LogViewer, StatusBadge, Layout.

6. **Phase 6 — Deployment** ✅: Multi-stage Dockerfile, docker-compose.yml, .gitignore.

7. **Phase 7 — Authentication & Authorization** ✅: Multi-user JWT auth, per-user API keys, 3-role RBAC (admin/operator/viewer). Frontend login page, settings page with API key management, admin user management. CLI bootstrap. 120 tests (94 backend + 26 frontend).

## Verification Plan

1. Start scheduler: `uvicorn cronbox.main:app`
2. Verify YAML loading: `GET /api/jobs` returns all 3 jobs with correct schedules
3. Trigger manually: `POST /api/jobs/polygon_sync/trigger` → check Docker container executes, log file appears in `logs/polygon_sync/`, run recorded in `GET /api/runs`
4. Verify failure handling: create a job with a deliberately bad command, trigger it, confirm it's marked failed and Discord notification fires
5. Frontend: open `http://localhost:8000`, redirected to `/login`, log in with admin credentials, confirm dashboard shows jobs, drill into job detail, view logs
6. Auth: verify viewer can read but not trigger, operator can trigger, admin can reload config and manage users
7. API keys: generate key in Settings page, use it via `curl -H "X-API-Key: cb_..."`, verify expiration
8. MCP STDIO: `python -m cronbox.mcp`, call `list_jobs` tool via Claude Desktop or fastmcp client
9. MCP HTTP: `python -m cronbox.mcp --transport http --port 9100`, verify tools at `http://localhost:9100`
10. Docker deployment: `docker compose up`, verify identical behavior

## Implementation Notes

### API Response Shapes

The REST API returns nested structures for job data:

- `GET /api/jobs` returns `JobSummary[]` with nested `schedule: {cron, timezone, enabled}` and `last_run: {status, started_at, duration_seconds} | null`
- `GET /api/jobs/{name}` returns `JobDetail` extending `JobSummary` with `container: {mode, name?, image?}`, `steps[]`, and `recent_runs[]`
- `GET /api/runs` returns `PaginatedRuns` with `{runs[], total, page, per_page}`
- `GET /api/runs/{id}` returns `RunDetail` with `steps[]` (step results) and `log_file`
- `GET /api/logs/{job_name}` returns `LogFileEntry[]` with `{filename, size_bytes, modified_at}`

### MCP Server Architecture

The MCP server uses module-level state initialized via an `@asynccontextmanager` lifespan passed to `FastMCP(lifespan=...)`. It creates its own `SchedulerEngine`, DB session factory, and `Settings` instance — fully standalone from the FastAPI server. Tools and resources access shared state through module globals set during lifespan initialization.

### Dockerfile

Uses a multi-stage build: first stage builds the frontend (Node.js + Vite), second stage installs Python deps and copies built frontend assets. This keeps the final image slim (python:3.12-slim, no Node.js).

### APScheduler 4.x — Serialization Constraint

APScheduler v4 requires all job callables to be module-level functions (not nested closures). It serializes them to dotted import references (e.g., `cronbox.main._execute_job_wrapper`) via `callable_to_ref()`. Dependencies that would normally be captured by closure must instead be passed via APScheduler's `kwargs` parameter on `add_schedule()`.

### APScheduler 4.x

Uses `AsyncScheduler` with manual `CronTrigger` field parsing (minute, hour, day, month, day_of_week) since APScheduler 4.x alpha may not have `from_crontab()`. `ConflictPolicy.replace` ensures config reloads update schedules in place.

## Python Dependencies

```toml
[project]
name = "cronbox"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "apscheduler==4.0.0a6",
    "sqlalchemy>=2.0",
    "aiosqlite>=0.20",
    "docker>=7.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "pydantic-settings>=2.0",
    "fastmcp>=2.0",
    "bcrypt>=4.0",
    "pyjwt>=2.8",
    "python-multipart>=0.0.9",
]

[project.scripts]
cronbox = "cronbox.cli:main"
```

## Frontend Dependencies

- react, react-dom, react-router-dom
- @tanstack/react-query
- @tanstack/react-virtual (LogViewer virtualization)
- tailwindcss (v4) + @tailwindcss/vite
- TypeScript, Vite, ESLint
