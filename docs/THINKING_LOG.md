# cronbox: Thinking & Decision Log

## 2026-02-11 — Initial Requirements Gathering

### Problem Statement

User has market-data jobs managed via crontab + shell scripts on a remote box. Current pain points:
- No visibility into job success/failure without SSHing in
- No centralized logs
- No notifications on failure
- No UI to inspect job state
- Shell scripts are fragile, mix Docker and host commands

### Existing Setup Analysis

**Crontab entries:**
```
00 04 * * 2-6 /home/si/market_data/run_polygon_sync.sh
00 08 * * 2-6 /home/si/market_data/run_etf_holdings.sh
30 23 * * 1-5 /home/si/market_data/run_vix_stuff.sh
```

**Key observations from scripts:**

1. **Shared persistent container**: All 3 jobs use the same `polygon_rip` container via `docker start` + `docker exec`. This is a common pattern when the container has expensive setup (data, dependencies, state) that you don't want to recreate each run.

2. **Multi-step jobs**: `run_vix_stuff.sh` runs two sequential Python scripts (regime.py, curvature.py). `run_etf_holdings.sh` runs a Docker exec then host-level wget commands.

3. **Mixed execution**: `run_etf_holdings.sh` mixes Docker commands with host-level `wget` and shell scripts. This is messy — part of the job runs containerized, part doesn't.

4. **Market-hours scheduling**: All jobs run on weekdays only (2-6 = Tue-Sat for the overnight jobs after Mon-Fri market close, 1-5 = Mon-Fri for the evening job).

---

## Decision: Backend Language → Python

**Options considered:**
- Python (APScheduler + FastAPI + Docker SDK)
- Node.js/TypeScript (node-cron + Express)
- Go (single binary, robfig/cron)

**Choice: Python**

Rationale:
- Docker SDK for Python is mature and well-documented
- APScheduler 4.x has async support, cron trigger parsing, and SQLAlchemy-backed state persistence
- FastAPI is fast to build and has automatic OpenAPI docs
- User's existing jobs are Python-heavy (regime.py, curvature.py, fetch_vixy_holdings.py), so staying in the same ecosystem makes sense
- Good for ops tooling — quick to iterate

---

## Decision: Job Config Format → YAML Files

**Options considered:**
- YAML/TOML files (version-controllable)
- SQLite database (UI-managed)
- Both (YAML source of truth, synced to DB)

**Choice: YAML files**

Rationale:
- Version controllable in git — can review changes, roll back
- Easy to copy between machines
- Human-readable, can be edited with any text editor
- One file per job keeps things modular
- DB adds complexity for config management with little benefit at this scale (3-10 jobs)
- Runtime state (run history) still goes to SQLite, just not the config

---

## Decision: Mixed Docker/Host Execution → All Docker

**Options considered:**
- Support both Docker and host-level steps in a single job
- All steps must run in Docker containers
- Keep host fallback for specific jobs

**Choice: All steps in Docker**

Rationale:
- Cleaner isolation — everything runs in a known environment
- Simpler execution engine — only one code path (Docker SDK)
- The host-level commands in `run_etf_holdings.sh` (wget, shell scripts) can easily be moved into a container
- Reduces attack surface — no arbitrary host command execution
- If a job needs files on the host, mount them as Docker volumes

**Migration note for etf_holdings**: The wget commands and `daily_fetch.sh` need to be containerized. Either add them as steps that exec into polygon_rip, or create a separate lightweight container with curl/wget.

---

## Decision: Container Model → Support Both Persistent and Ephemeral

**Options considered:**
- Fresh ephemeral containers only (docker run --rm)
- Persistent containers only (docker start + exec)
- Support both modes

**Choice: Support both**

Rationale:
- User's current setup relies on a persistent container (polygon_rip) — must support this
- Ephemeral containers are cleaner for jobs that don't need shared state
- The config schema handles this cleanly with a `mode` field: `persistent` or `ephemeral`
- Docker SDK handles both patterns well
- Persistent mode: `ensure_started()` + `exec_run()`
- Ephemeral mode: `containers.run(remove=True)`

---

## Decision: Log Storage → Disk Files

**Options considered:**
- SQLite (store stdout/stderr as text blobs)
- Log files on disk (timestamped per run)
- Both (SQLite for quick access, files for archival)

**Choice: Log files on disk**

Rationale:
- Logs can be large — don't want to bloat SQLite
- Easy to inspect manually: `cat logs/polygon_sync/2026-02-11T04-00-00Z.log`
- Easy to clean up: just delete old files
- SQLite stores metadata (run status, duration, exit codes) but not full output
- API serves log file content directly via file read
- Simple retention: delete files older than N days

**Directory structure:**
```
logs/
├── polygon_sync/
│   ├── 2026-02-11T04-00-00Z.log
│   └── 2026-02-12T04-00-00Z.log
├── etf_holdings/
│   └── ...
└── vix_stuff/
    └── ...
```

---

## Decision: Notifications → Discord Webhook

**Options considered:**
- None (UI only)
- Slack webhook
- Email
- Discord webhook

**Choice: Discord webhook**

Rationale:
- User preference
- Simple HTTP POST with JSON payload — no SDK needed, just httpx
- Rich embeds supported (colored sidebar, fields for job name, failed step, duration)
- Configurable globally via `CRONBOX_DISCORD_WEBHOOK_URL` env var
- Per-job override possible via `notify.discord_webhook_url` in YAML
- Only on failure by default (configurable per-job)

---

## Decision: Frontend → React SPA

**Options considered:**
- Server-rendered HTML (HTMX/plain)
- React SPA
- Terminal UI only

**Choice: React SPA**

Rationale:
- User preference
- TanStack Query makes auto-polling trivial
- Tailwind CSS for fast, clean styling without a component library
- Three simple views: dashboard, job detail, log viewer
- Built as static files, served by FastAPI's StaticFiles mount — no separate server needed
- Vite for fast dev experience

---

## Decision: Deployment → Flexible (Host or Docker)

**Options considered:**
- Host only
- Docker only (scheduler runs in container)
- Flexible / both

**Choice: Flexible**

Rationale:
- Docker SDK connects via `/var/run/docker.sock` regardless of where the scheduler runs
- Running on host: socket is available natively
- Running in Docker: mount the socket as a volume
- docker-compose.yml provided for containerized deployment
- `pip install -e . && uvicorn` for host deployment
- Same codebase, same behavior, just different deployment wrapper

---

## Decision: Scheduler Library → APScheduler 4.x

**Why APScheduler 4:**
- Native async support (fits FastAPI's async model)
- `CronTrigger.from_crontab()` parses standard 5-field cron expressions directly — user's existing crontab entries copy verbatim
- SQLAlchemy data store persists schedule state across restarts (next fire times, avoiding missed/duplicate runs)
- `ConflictPolicy.replace` handles config reloads cleanly — re-adding a schedule with the same ID updates it in place
- Mature, well-maintained, widely used

---

## Decision: MCP Server → FastMCP for LLM Access

**Context**: Add a way for LLMs (Claude Desktop, Claude Code, etc.) to programmatically query cronbox status and control jobs.

**Options considered:**
- No MCP, REST API only (LLMs would need custom HTTP tool wrappers)
- Custom MCP implementation from scratch
- FastMCP framework

**Choice: FastMCP**

Rationale:
- FastMCP is the standard Python framework for building MCP servers — clean decorator-based API
- Supports both STDIO transport (for Claude Desktop / local LLM tools) and HTTP transport (for remote access) out of the box
- `@mcp.tool` decorator maps naturally to cronbox operations (list_jobs, trigger_job, get_log, etc.)
- `@mcp.resource` decorator exposes read-only data (job configs, system status)
- Runs as a separate entrypoint (`python -m cronbox.mcp`) — no coupling to the FastAPI server
- Reuses all internal cronbox modules (loader, database, runner) — no logic duplication
- Minimal new code: one server.py file defining tools + resources, one __main__.py for the CLI entrypoint

**Transport design:**
- **STDIO** (default): `python -m cronbox.mcp` — for local LLM integration (Claude Desktop, Claude Code)
- **HTTP**: `python -m cronbox.mcp --transport http --port 9100` — for remote access, runs on port 9100 (separate from FastAPI on 8000)

**Tools exposed (7):**
- `list_jobs` — all jobs with schedule, next run, last status
- `get_job` — single job detail + recent runs
- `trigger_job` — immediate manual run
- `list_runs` — run history (filterable by job)
- `get_run` — run detail with per-step results
- `get_log` — log content (latest or by run_id)
- `reload_config` — hot-reload YAML configs

**Resources exposed (3):**
- `cronbox://jobs` — all job configs as JSON
- `cronbox://jobs/{name}` — single job config as YAML
- `cronbox://status` — system status (uptime, job counts, recent failures)

### MCP Access Level: Read + Trigger Only (No Config Mutation)

**Question**: Should LLMs be able to create/update/delete job configs through MCP?

**Options considered:**
- Read + trigger only — MCP queries status and triggers runs, config changes require editing YAML files
- Full CRUD — MCP writes YAML files on disk, reloads scheduler
- Full CRUD + git auto-commit — same but with audit trail

**Choice: Read + trigger only**

Rationale:
- YAML files stay the single source of truth — no risk of LLM accidentally breaking schedules
- Config changes are deliberate, reviewable actions (edit a file, commit to git)
- Claude Code can still edit YAML files directly when asked — the MCP server just doesn't expose that as a tool
- Keeps the MCP attack surface minimal: worst case an LLM can trigger a job to run early, not rewrite its definition
- `reload_config` tool is the bridge: after a human (or Claude Code) edits YAML, an LLM can reload the scheduler

---

---

## 2026-02-11 — Implementation Complete

### What Was Built

All 6 phases implemented in a single session. 50 files, ~6,250 lines of code across backend, frontend, and MCP server.

### Implementation Decisions Made During Build

#### APScheduler 4.x CronTrigger — Manual Field Parsing

APScheduler 4.x (alpha) doesn't expose `CronTrigger.from_crontab()` reliably. Instead, the scheduler engine splits the 5-field cron string and passes individual fields (`minute`, `hour`, `day`, `month`, `day_of_week`) to `CronTrigger()`. This works identically and avoids depending on an unstable API.

#### API Response Shapes — Nested vs Flat

Initial backend implementation used flat fields (`cron`, `timezone`, `enabled`, `last_status`, `last_run_at`) on `JobSummary`. The frontend was designed with nested structures (`schedule: {cron, timezone, enabled}`, `last_run: {status, started_at, duration_seconds}`). Resolved by updating the backend API models to use nested structures — cleaner API contract and matches the PLAN.md spec. Required updating `api_models.py` and `routes_jobs.py`.

#### MCP Server — Module-Level State vs Lifespan Context

Initial MCP implementation used `from fastmcp.server.lifespan import lifespan` decorator and `ctx.lifespan_context` to access shared state. This pattern isn't documented in FastMCP 2.0. Rewrote to use `@asynccontextmanager` from stdlib as the lifespan, with module-level globals for shared state (`_settings`, `_session_factory`, `_engine`, `_startup_time`). Tools access these globals directly. Simpler, more reliable, no dependency on undocumented FastMCP internals.

#### MCP Server — Standalone Operation

The MCP server creates its own `SchedulerEngine`, DB session factory, and `Settings` instance during its lifespan. It does not depend on the FastAPI server running. This means `python -m cronbox.mcp` works independently — important for Claude Desktop integration where the MCP server runs as a subprocess.

#### Dockerfile — Multi-Stage Build

Initial Dockerfile had a build order bug: `pip install .` ran before `src/` was copied, which fails because setuptools needs the source. Fixed with a multi-stage build: stage 1 builds the frontend (Node.js), stage 2 installs Python deps with source present, then copies the frontend build artifact. Keeps the final image slim (no Node.js in production).

#### Tailwind CSS v4

Frontend uses Tailwind CSS v4 which has a different setup than v3: no `tailwind.config.js` needed, just `@import "tailwindcss"` in the CSS entry point and the `@tailwindcss/vite` plugin.

#### Frontend LogViewer — Path Extraction

The `log_file` field in run details is a full path (e.g., `logs/polygon_sync/20260211_040000.log`), but the log API endpoint expects just the filename. LogViewer extracts the filename with `logFile.split("/").pop()`.

---

## Open Questions / Future Considerations

- **Market calendar awareness**: Jobs run on weekday schedules, but markets also close on holidays. Could add a market calendar check (e.g., `exchange_calendars` library) that skips runs on market holidays. Not in v1.
- **Job dependencies**: No job-to-job dependency support in v1. If needed later, could add a `depends_on` field.
- **Config hot-reload via filesystem watcher**: v1 uses a manual `POST /api/config/reload` endpoint. Could add `watchfiles` to auto-detect YAML changes later.
- **Authentication**: The web UI has no auth in v1. Fine for local/VPN access. Could add basic auth or API key later.
- **WebSocket for live logs**: v1 polls for log content. Could upgrade to WebSocket streaming for real-time log following.
- **Log retention cleanup**: `CRONBOX_LOG_RETENTION_DAYS` is configured but the cleanup task is not yet implemented. Needs a periodic job that deletes log files older than the threshold.
- **Tests**: No test suite yet. Priority areas: YAML loader validation, API route responses, runner step execution logic, Docker ops mocking.
