# cronbox: Job Scheduler & Runner

## Context

Replace ad-hoc crontab + shell scripts with a proper job scheduler that runs all jobs in Docker containers, captures logs, tracks success/failure, sends Discord alerts on failure, and provides a web UI dashboard. The user's current setup has 3 market-data jobs running on weekdays via crontab, using `docker start` + `docker exec` on a persistent `polygon_rip` container.

## Stack

- **Backend**: Python 3.12+ — FastAPI (API + static file serving), APScheduler 4.x (scheduling), Docker SDK (container ops), SQLAlchemy + aiosqlite (run history), httpx (Discord webhooks)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query
- **Config**: YAML files in `config/jobs/` (one per job)
- **Storage**: SQLite for run metadata, disk files for logs

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
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job_config.py            # Pydantic models for YAML schema
│   │   ├── database.py              # SQLAlchemy models (job_runs, step_results)
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
│       ├── routes_jobs.py           # /api/jobs — list, detail, trigger, reload
│       ├── routes_runs.py           # /api/runs — run history + detail
│       └── routes_logs.py           # /api/logs — log file listing + content
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                   # Router: / → JobList, /jobs/:name → JobDetail
│       ├── api.ts                    # Fetch wrapper for REST API
│       ├── types.ts                  # TypeScript types mirroring API models
│       └── components/
│           ├── Layout.tsx            # Shell with header + nav
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

## API Endpoints

All routes prefixed with `/api`. Frontend served at `/` as static files.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/jobs` | List all jobs with next run time + last status |
| GET | `/api/jobs/{name}` | Job detail + step list + recent runs |
| POST | `/api/jobs/{name}/trigger` | Trigger immediate manual run |
| POST | `/api/config/reload` | Hot-reload YAML configs into scheduler |
| GET | `/api/runs` | List recent runs across all jobs (paginated) |
| GET | `/api/runs?job_name=X` | Filter runs by job name |
| GET | `/api/runs/{id}` | Run detail with step results |
| GET | `/api/logs/{job_name}` | List log files for a job |
| GET | `/api/logs/{job_name}/{filename}` | Get log file contents (plain text) |

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

## Frontend

Single-page React app with three views:

### Dashboard (`/`)
- Table of all jobs: Name, Schedule (human-readable), Next Run, Last Status, Last Run Time, Actions (trigger button)
- Status badges: green=success, red=failed, gray=never run, blue spinner=running
- Auto-polls `GET /api/jobs` every 10 seconds

### Job Detail (`/jobs/:name`)
- Header: job name, description, cron schedule
- "Trigger Now" button → `POST /api/jobs/{name}/trigger`
- Steps list: step name + command
- Run history table (last 50): Status, Started, Duration, Trigger type
- Each run row expands/links to show step results + log

### Log Viewer (within job detail)
- Fetches log content as plain text
- Monospace, dark-themed scrollable container
- Highlights `[STDOUT]`, `[STDERR]`, exit codes, failure markers
- Auto-scrolls to bottom, "follow" toggle for in-progress runs (re-fetches every 3s)

## Configuration

All settings via environment variables prefixed with `CRONBOX_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRONBOX_JOBS_CONFIG_DIR` | `config/jobs` | Path to YAML job files |
| `CRONBOX_LOGS_DIR` | `logs` | Path to log file directory |
| `CRONBOX_DB_PATH` | `data/cronbox.db` | SQLite database path |
| `CRONBOX_DISCORD_WEBHOOK_URL` | (empty) | Global Discord webhook URL |
| `CRONBOX_WEB_BASE_URL` | (empty) | Base URL for links in notifications |
| `CRONBOX_API_HOST` | `0.0.0.0` | API listen host |
| `CRONBOX_API_PORT` | `8000` | API listen port |
| `CRONBOX_LOG_RETENTION_DAYS` | `30` | Auto-delete logs older than this |

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
      - CRONBOX_DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
      - CRONBOX_WEB_BASE_URL=${WEB_BASE_URL:-http://localhost:8000}
    restart: unless-stopped
```

### Direct on host

```bash
pip install -e .
uvicorn cronbox.main:app --host 0.0.0.0 --port 8000
```

Both modes work — Docker SDK uses `/var/run/docker.sock` either directly on host or via socket mount.

## Build Phases

1. **Phase 1 — Core engine** (no UI, no API): config.py, job_config.py, loader.py, docker_ops.py, log_capture.py, runner.py, engine.py, YAML job files. **Test**: run scheduler, trigger a job, verify Docker exec works and logs are written to disk.

2. **Phase 2 — Persistence + API**: database.py, api_models.py, route files, main.py. Wire runner to write to SQLite. **Test**: curl endpoints, verify JSON responses match expected shapes.

3. **Phase 3 — Notifications**: discord.py, wire into runner failure path. **Test**: deliberately fail a job, verify Discord embed appears.

4. **Phase 4 — MCP server**: mcp/server.py (FastMCP tools + resources), mcp/__main__.py (CLI entrypoint). **Test**: `python -m cronbox.mcp` via STDIO, `--transport http --port 9100` via HTTP.

5. **Phase 5 — Frontend**: Scaffold Vite + React + TS + Tailwind, build components (JobList, JobDetail, LogViewer), wire up TanStack Query polling. **Test**: full end-to-end in browser.

6. **Phase 6 — Deployment + polish**: Dockerfile, docker-compose.yml, log retention cleanup task, config reload endpoint.

## Verification Plan

1. Start scheduler: `uvicorn cronbox.main:app`
2. Verify YAML loading: `GET /api/jobs` returns all 3 jobs with correct schedules
3. Trigger manually: `POST /api/jobs/polygon_sync/trigger` → check Docker container executes, log file appears in `logs/polygon_sync/`, run recorded in `GET /api/runs`
4. Verify failure handling: create a job with a deliberately bad command, trigger it, confirm it's marked failed and Discord notification fires
5. Frontend: open `http://localhost:8000`, confirm dashboard shows jobs, drill into job detail, view logs
6. MCP STDIO: `python -m cronbox.mcp`, call `list_jobs` tool via Claude Desktop or fastmcp client
7. MCP HTTP: `python -m cronbox.mcp --transport http --port 9100`, verify tools at `http://localhost:9100`
8. Docker deployment: `docker compose up`, verify identical behavior

## Python Dependencies

```toml
[project]
name = "cronbox"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "apscheduler>=4.0",
    "sqlalchemy>=2.0",
    "aiosqlite>=0.20",
    "docker>=7.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "pydantic-settings>=2.0",
    "fastmcp>=2.0",
]
```
