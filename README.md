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
- **YAML config** — version-controllable job definitions, one file per job

## Quick Start

### Prerequisites

- Python 3.12+
- Docker (running)
- Node.js 20+ (for frontend development)

### Install & Run

```bash
# Install Python dependencies
pip install -e .

# Start the scheduler + API server
uvicorn cronbox.main:app --host 0.0.0.0 --port 8000
```

### With Docker Compose

```bash
docker compose up -d
```

The web UI is available at `http://localhost:8000`.

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
| `CRONBOX_JOBS_CONFIG_DIR` | `config/jobs` | Path to YAML job files |
| `CRONBOX_LOGS_DIR` | `logs` | Log file directory |
| `CRONBOX_DB_PATH` | `data/cronbox.db` | SQLite database path |
| `CRONBOX_DISCORD_WEBHOOK_URL` | | Discord webhook for failure alerts |
| `CRONBOX_WEB_BASE_URL` | | Base URL for notification links |
| `CRONBOX_LOG_RETENTION_DAYS` | `30` | Auto-delete logs older than this |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/{name}` | Job detail + recent runs |
| POST | `/api/jobs/{name}/trigger` | Trigger a manual run |
| POST | `/api/config/reload` | Reload YAML configs |
| GET | `/api/runs?job_name=X` | Run history |
| GET | `/api/runs/{id}` | Run detail with step results |
| GET | `/api/logs/{job_name}` | List log files |
| GET | `/api/logs/{job_name}/{filename}` | Log file content |

## Project Structure

```
├── config/jobs/          # YAML job definitions
├── src/cronbox/       # Python backend
│   ├── main.py           # FastAPI app
│   ├── scheduler/        # APScheduler engine + YAML loader
│   ├── executor/         # Docker execution + log capture
│   ├── notifications/    # Discord webhooks
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
