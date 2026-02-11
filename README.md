# cronbox

A job scheduler and runner that manages and executes jobs inside Docker containers on configurable schedules. Think cron, but with a web UI, execution logs, and Discord failure alerts.

## Features

- **Cron-style scheduling** — standard 5-field cron expressions with timezone support
- **Docker execution** — all jobs run inside Docker containers (persistent or ephemeral)
- **Multi-step jobs** — jobs can have multiple sequential steps, failing fast on errors
- **Execution logs** — stdout/stderr captured to timestamped log files per run
- **Run history** — success/failure tracking with duration and per-step results
- **Discord alerts** — webhook notifications on job failure
- **Web dashboard** — React SPA showing job status, run history, and log viewer
- **MCP server** — LLMs can query status and control jobs via FastMCP (STDIO + HTTP)
- **YAML config** — version-controllable job definitions, one file per job

## Quick Start (Docker Compose)

### 1. Create a `.env` file

```bash
cp .env.example .env
```

Generate a JWT secret and write it into `.env`:

```bash
# macOS / Linux
openssl rand -hex 32
```

Copy the output and paste it as the `JWT_SECRET` value in `.env`. This secret signs all authentication tokens — keep it private and don't commit it.

### 3. Build and start

```bash
docker compose up -d
```

### 4. Create the admin user

```bash
docker compose exec cronbox cronbox create-user \
  --username admin \
  --email admin@example.com \
  --role admin \
  --password 'your-password-here'
```

### 5. Log in

Open `http://localhost:8000` and sign in with the admin credentials.

### Local Development (no Docker)

```bash
pip install -e .

# No JWT_SECRET = dev mode (no auth required)
uvicorn cronbox.main:app --reload
```

## Job Configuration

Jobs are defined as YAML files in `config/jobs/`. Each file defines one job.

### Example: Persistent container (exec into existing container)

```yaml
name: polygon_sync
description: "Daily polygon data sync"

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

### Example: Ephemeral container (fresh container per run)

```yaml
name: data_export
description: "Weekly data export"

schedule:
  cron: "0 2 * * 0"
  timezone: "America/New_York"

container:
  mode: ephemeral
  image: "myregistry/exporter:latest"
  volumes:
    "/host/data": "/output"

steps:
  - name: export
    command: "python /app/export.py"

notify:
  on_failure: true
  on_success: true
```

## Configuration

All settings are configurable via environment variables prefixed with `CRONBOX_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRONBOX_JWT_SECRET` | | **Required for auth.** JWT signing secret. Empty = dev mode (no auth). |
| `CRONBOX_JOBS_CONFIG_DIR` | `config/jobs` | Path to YAML job files |
| `CRONBOX_LOGS_DIR` | `logs` | Log file directory |
| `CRONBOX_DB_PATH` | `data/cronbox.db` | SQLite database path |
| `CRONBOX_DISCORD_WEBHOOK_URL` | | Discord webhook for failure alerts |
| `CRONBOX_WEB_BASE_URL` | | Base URL for notification links |
| `CRONBOX_LOG_RETENTION_DAYS` | `30` | Auto-delete logs older than this |
| `CRONBOX_MCP_API_KEY` | | API key for MCP server authentication |

## Authentication

cronbox supports three auth modes based on configuration:

| `JWT_SECRET` | Behavior |
|---|---|
| empty | Dev mode — no auth required |
| set | Full multi-user auth (JWT + per-user API keys + RBAC) |

**Roles:** `admin` (full access), `operator` (read + trigger jobs), `viewer` (read-only).

Programmatic access uses per-user API keys (generated in Settings page), passed via `X-API-Key` header.

## API

All endpoints except `/api/auth/*` require authentication when `JWT_SECRET` is set.

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | — | Login with username/password |
| POST | `/api/auth/refresh` | — | Refresh access token |
| GET | `/api/jobs` | viewer+ | List all jobs |
| GET | `/api/jobs/{name}` | viewer+ | Job detail + recent runs |
| POST | `/api/jobs/{name}/trigger` | operator+ | Trigger a manual run |
| POST | `/api/config/reload` | admin | Reload YAML configs |
| GET | `/api/runs?job_name=X` | viewer+ | Run history |
| GET | `/api/runs/{id}` | viewer+ | Run detail with step results |
| GET | `/api/logs/{job_name}` | viewer+ | List log files |
| GET | `/api/logs/{job_name}/{filename}` | viewer+ | Log file content |
| GET | `/api/keys` | viewer+ | List your API keys |
| POST | `/api/keys` | viewer+ | Generate new API key |
| GET | `/api/admin/users` | admin | List all users |
| POST | `/api/admin/users` | admin | Create user |

## MCP Server

cronbox includes an MCP (Model Context Protocol) server so LLMs can query job status and trigger runs programmatically. The MCP server is read-only for configs — job definitions can only be changed by editing YAML files directly.

### STDIO (Claude Desktop / Claude Code)

```bash
python -m cronbox.mcp
```

Claude Desktop config:
```json
{
  "mcpServers": {
    "cronbox": {
      "command": "python",
      "args": ["-m", "cronbox.mcp"],
      "cwd": "/path/to/cronbox"
    }
  }
}
```

### HTTP (remote access)

```bash
python -m cronbox.mcp --transport http --port 9100
```

### Available Tools

| Tool | Description |
|------|-------------|
| `list_jobs` | List all jobs with schedule, next run, last status |
| `get_job` | Get job config + recent runs |
| `trigger_job` | Trigger an immediate manual run |
| `list_runs` | List recent runs (filterable by job) |
| `get_run` | Get run detail with per-step results |
| `get_log` | Get log content for a run |
| `reload_config` | Hot-reload YAML job configs |

## Project Structure

```
├── config/jobs/          # YAML job definitions
├── src/cronbox/          # Python backend
│   ├── main.py           # FastAPI app
│   ├── scheduler/        # APScheduler engine + YAML loader
│   ├── executor/         # Docker execution + log capture
│   ├── notifications/    # Discord webhooks
│   ├── mcp/              # FastMCP server (STDIO + HTTP)
│   └── api/              # REST API routes
├── frontend/             # React SPA
├── docs/                 # Design docs
│   ├── PLAN.md           # Implementation plan
│   └── THINKING_LOG.md   # Decision log
├── logs/                 # Runtime: execution logs
└── data/                 # Runtime: SQLite database
```

## Development

```bash
# Backend
pip install -e ".[dev]"
uvicorn cronbox.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```
