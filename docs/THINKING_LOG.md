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

## 2026-02-11 — Code Review (Security, Performance, Test Coverage)

Ran a parallel 3-agent code review across the full codebase. 32 findings total (6 critical, 13 high, 12 medium, 1 low). Full details in `docs/REVIEW_LOG.md`.

### Key Takeaways

**Security — no auth + path traversal are the top issues.**
- The API has zero authentication on any endpoint. Combined with the default `0.0.0.0` bind, anyone on the network can trigger jobs, read logs, and reload config. The "Authentication" bullet in Open Questions below was already flagged — the review confirmed it's the #1 priority.
- `list_logs` in `routes_logs.py` has a path traversal bug: `job_name` is joined into the log directory path with no `resolve()+startswith()` check, even though the sibling `get_log` endpoint correctly validates. Same pattern missing in MCP `get_log` (two code paths, neither validated).
- API responses leak full server filesystem paths (`log_file` field).

**Performance — N+1 queries and unbounded reads are the main concerns.**
- `list_jobs` in both the API and MCP server opens a new DB session and runs a separate query per job to get its last run status. With 50 jobs = 50 round-trips per dashboard load.
- `get_next_run_time` iterates all APScheduler schedules for each job (O(n) per call, O(n^2) in the list_jobs loop). Should use direct `get_schedule(id)` lookup.
- Log file reads (`routes_logs.py` and `mcp/server.py`) load entire files into memory with no size cap. Large Docker job logs could OOM the process.
- `DockerOperations` is instantiated per job execution instead of being shared. Container is also looked up twice per step (once in `ensure_started`, once in `exec_in_container`).
- Frontend `LogViewer` creates a DOM node per log line with no virtualization — will choke on large logs.

**Test coverage — zero tests exist.**
- No test files, no test infrastructure, no pytest or vitest configured anywhere.
- Every module is untested — executor, scheduler, API routes, MCP tools, notifications, models, frontend components.
- The path traversal security guard in `get_log` has no tests verifying it works.

### Decisions / Next Steps

The review surfaced several items that were already noted as open questions (auth, tests). Updated priorities based on actual findings:

1. ~~**Fix path traversal bugs**~~ — **DONE** (a2faac1). Added `resolve()+startswith()` to `list_logs` and MCP `get_log`. MCP error messages no longer leak paths. → [#1](https://github.com/sjwe/cronbox/issues/1) (closed)
2. ~~**Add authentication**~~ — **DONE** (pending commit). API key middleware on all API routes + default bind changed to `127.0.0.1`. → [#2](https://github.com/sjwe/cronbox/issues/2) (closed)
3. ~~**Add test infrastructure + critical tests**~~ — **DONE** (ac834ad). → [#5](https://github.com/sjwe/cronbox/issues/5) (closed)
4. ~~**Batch N+1 queries**~~ — **DONE** (a2faac1). `ROW_NUMBER()` window function in shared `models/queries.py`. `get_all_next_run_times()` batch method. → [#3](https://github.com/sjwe/cronbox/issues/3) (closed)
5. ~~**Cap log file reads**~~ — **DONE** (a2faac1). `read_log_tail()` in `utils.py` caps at 1MB. `list_logs` paginated with `?limit=N`. → [#4](https://github.com/sjwe/cronbox/issues/4) (closed)

---

## 2026-02-11 — Test Infrastructure Added

Added test infrastructure and 72 tests (52 backend, 20 frontend) in `ac834ad`. Closes [#5](https://github.com/sjwe/cronbox/issues/5).

### What Was Built

**Python backend (52 tests in 6 files):**
- `conftest.py` with 7 shared fixtures: in-memory SQLite engine/session, test `Settings` with temp dirs, mock `DockerOperations`, FastAPI `AsyncClient` via `ASGITransport`, sample `JobConfig`
- `test_loader.py` (8) — YAML config loading: valid configs, empty/nonexistent dirs, non-yaml skipped, empty YAML skipped, missing fields raises ValidationError
- `test_job_config.py` (18) — All Pydantic models: StepConfig, ContainerConfig, ScheduleConfig, NotifyConfig, JobConfig — required/optional fields, defaults, validation errors
- `test_docker_ops.py` (9) — Docker ops with mocked client: ensure_started, exec_in_container (demuxed/bytes/options), run_ephemeral (basic/options/none), close
- `test_routes_logs.py` (6) — Log routes including **path traversal security test** (verifies `../` returns 403)
- `test_routes_jobs.py` (7) — Job API: list empty/with jobs/with last run, get existing/404, trigger existing/404
- `test_discord.py` (4) — Discord notifications: empty webhook early return, embed structure, log_url conditional

**TypeScript frontend (20 tests in 3 files):**
- vitest + jsdom configured in `vite.config.ts`
- `JobList.test.ts` (7) — `parseCronSchedule` (5 cron patterns incl. midnight edge case) + `relativeTime` (past/future)
- `LogViewer.test.ts` (7) — `highlightLine` for STDERR/STDOUT/exit codes/keywords/plain
- `api.test.ts` (6) — fetchJobs, fetchJSON error, triggerJob POST, fetchRuns query building, fetchLogContent text

### Decisions Made During Build

**Exported internal functions for testing:** `parseCronSchedule`, `relativeTime` (JobList.tsx), and `highlightLine` (LogViewer.tsx) were internal functions. Added named exports so vitest can import them directly. Default component exports unchanged.

**FastAPI test client approach:** Used httpx `AsyncClient` with `ASGITransport` rather than FastAPI's sync `TestClient`. This allows proper async test execution matching the app's async handlers. The `async_client` fixture bypasses the app lifespan and injects test state (in-memory DB, mock scheduler) directly onto `app.state`.

**Test runner path:** The correct Python/pytest is the conda base at `/opt/homebrew/Caskroom/miniconda/base/bin/python -m pytest` — the PATH `python` may point to a different project's venv.

### Remaining Gaps

Placeholder test files exist for 6 modules — to be filled incrementally:
- `test_runner.py` — executor step sequencing, timeouts, failure cascading (most complex, needs careful mocking)
- `test_engine.py` — APScheduler lifecycle, cron registration
- `test_database.py` — ORM relationships, schema creation, cascade delete
- `test_routes_runs.py` — pagination, job_name filtering
- `test_config.py` — pydantic-settings env var loading with CRONBOX_ prefix
- `test_server.py` — MCP tools and resources (7 tools, 3 resources)

---

## 2026-02-11 — High Priority Fixes (#1, #3, #4)

Fixed the three highest-priority open issues in `a2faac1`. All 58 tests pass (was 52 before, +6 new tests).

### Issue #1: Path Traversal Vulnerabilities

**`routes_logs.py` — `list_logs`**: Added `resolve()+startswith()` guard after constructing `log_dir`, before iterating. Returns 403 on traversal. The sibling `get_log` already had this — was just missing from `list_logs`.

**`mcp/server.py` — `get_log`**: Two code paths, both now validated:
- DB-stored `run.log_file` path — validated against logs base dir (prevents a compromised DB row from reading arbitrary files)
- User-supplied `job_name` joined into path — validated against logs base dir

**MCP error messages**: Changed `f"Log file not found: {log_path}"` to generic `"Log file not found"` — stops leaking server filesystem paths to MCP clients.

### Issue #3: N+1 Queries in list_jobs

**New `models/queries.py`**: Shared `get_latest_runs(session)` helper using `ROW_NUMBER()` window function partitioned by `job_name`, ordered by `started_at desc`. Returns `dict[str, JobRun]` — one query for all jobs.

**`scheduler/engine.py`**: `get_next_run_time()` now uses `get_schedule(id)` for O(1) lookup instead of fetching all schedules. New `get_all_next_run_times()` batch method fetches all schedules once and returns a dict. The `list_jobs` endpoints use the batch method.

**Both API and MCP `list_jobs`** now use 1 DB session + 1 query + 1 scheduler call, down from N of each.

### Issue #4: Unbounded Log File Reads

**New `utils.py`**: Shared `read_log_tail(path, max_bytes=1_048_576)` helper. For files under 1MB, reads normally. For larger files, seeks to last 1MB, skips the partial first line, prepends `[... truncated, showing last 1024KB of N bytes ...]` header.

**`list_logs` pagination**: Added `?limit=N` query param (default 100) to prevent unbounded directory listings.

Both API `get_log` and MCP `get_log` now use `read_log_tail()`.

### New files
- `src/cronbox/models/queries.py` — shared batch query helper
- `src/cronbox/utils.py` — shared log tail reader

---

## 2026-02-11 — Second Round Fixes (#2, #7, #9)

Fixed the remaining high-priority issue and two medium issues. 69 tests pass (was 58 before, +11 new tests).

### Issue #2: API Authentication

**`config.py`**: Changed default `api_host` from `0.0.0.0` to `127.0.0.1`. Added `api_key: str = ""` setting (empty = no auth, for local dev).

**New `api/auth.py`**: `verify_api_key` FastAPI dependency that checks `X-API-Key` header or `Authorization: Bearer` header against `settings.api_key`. When `api_key` is empty, all requests pass through — existing tests unaffected.

**`main.py`**: Added `Depends(verify_api_key)` to all 3 API router includes. Frontend static files are NOT auth-gated (served via separate `StaticFiles` mount).

**Design choice — auth on all routes, not just mutating**: Even read endpoints expose sensitive data (logs, job configs, run history). Protecting only POST endpoints would still leak information. Simple API key is appropriate for a single-user ops tool; can upgrade to JWT later if multi-user is needed.

### Issue #7: Harden Background Task

**`routes_jobs.py`**:
- `_running_tasks: dict[str, asyncio.Task]` tracks active background tasks by job name
- `_task_done_callback()` cleans up the dict and logs warnings/errors for cancelled or failed tasks (no more silent exception swallowing)
- Concurrency guard: returns 409 Conflict if a trigger request comes in while the same job is already running

### Issue #9: Stop Leaking Filesystem Paths

**`routes_runs.py` and `mcp/server.py`**: `log_file` field stripped from full path (e.g., `logs/test-job/20240101.log` or `/home/user/cronbox/logs/test-job/20240101.log`) to just `job_name/filename` (e.g., `test-job/20240101.log`). Handles both relative and absolute stored paths.

**Frontend note**: The frontend `LogViewer` already extracted the filename with `.split("/").pop()`, so stripping the prefix is backwards-compatible — it still gets the filename it needs.

### New files
- `src/cronbox/api/auth.py` — API key authentication dependency
- `tests/api/test_auth.py` — 6 auth tests

---

## 2026-02-11 — Authentication System Design

### Problem

The single shared API key (`CRONBOX_API_KEY`) is insufficient for multi-user deployment:
- No per-user credentials or identity tracking
- No frontend login — the UI is either fully open or inaccessible
- No per-user API keys for programmatic access
- No role-based access control — any authenticated user can do everything
- API keys have no expiration

### Decision: JWT + Per-User API Keys + 3-Role RBAC

**Auth mechanisms (3, coexisting):**

1. **JWT access/refresh tokens** for browser sessions. Access tokens (15min) in localStorage, refresh tokens (7 days) as httpOnly cookies. Login via username/password form.
2. **Per-user API keys** for programmatic and MCP access. Format: `cb_` prefix + random bytes, SHA-256 hashed for storage. Returned once on creation, 30-day default expiration.
3. **Legacy shared API key** (`CRONBOX_API_KEY`) for backwards compatibility during migration.

**Why JWT + API keys (not just one):**
- JWTs are ideal for browser sessions: short-lived, stateless verification, automatic refresh
- API keys are ideal for scripts/MCP: long-lived, simple header inclusion, no login flow needed
- Both resolve to the same User object and go through the same RBAC checks

**Password hashing:** bcrypt via `passlib`. Industry standard, slow-by-design for brute-force resistance.

**API key hashing:** SHA-256. Fast verification is fine here since keys are high-entropy random tokens (not passwords). Prefixed with `cb_` for easy identification.

### Decision: 3 Roles (admin / operator / viewer)

| Role | Capabilities |
|------|-------------|
| **viewer** | Read all jobs, runs, logs. Manage own API keys. |
| **operator** | Everything viewer can do + trigger jobs |
| **admin** | Everything operator can do + reload config, manage users |

**Enforcement:** FastAPI dependency injection. `require_role()` factory returns a `Depends()` callable that checks the current user's role. Applied per-endpoint where the default auth isn't sufficient.

**Why not just admin/viewer:** The operator role covers the common case of a team member who needs to manually trigger jobs (e.g., re-run a failed data sync) but shouldn't be able to change scheduler config or create users.

### Decision: CLI Bootstrap (not open registration)

**Choice:** `cronbox create-user --username admin --email admin@example.com --role admin`

**Why not open registration:** This is an ops tool, not a SaaS product. The admin controls who has access. Open registration would require invitation/approval workflow complexity.

**Why not env var seed:** Env vars are visible in process listings and Docker inspect. A CLI command with password prompting is more secure for the initial setup.

### Decision: Full Backwards Compatibility

Auth behavior is determined by which env vars are set:
- No `JWT_SECRET`, no `API_KEY` → dev mode (no auth, same as original behavior)
- No `JWT_SECRET`, `API_KEY` set → legacy single-key auth (current behavior)
- `JWT_SECRET` set → full multi-user auth system

This means existing deployments continue working unchanged. Users migrate at their own pace by setting `CRONBOX_JWT_SECRET` and running `cronbox create-user`.

### Decision: Refresh Token in httpOnly Cookie

**Why not localStorage for refresh token:** XSS attacks can steal tokens from localStorage. httpOnly cookies are inaccessible to JavaScript, limiting the blast radius of XSS.

**Why access token stays in localStorage:** The access token must be included in the `Authorization` header for API requests, which requires JavaScript access. It's short-lived (15min), limiting exposure.

**API client fallback:** The refresh token is also returned in the login response body for non-browser clients (scripts, MCP) that can't use cookies.

### Decision: MCP Auth via Pre-configured API Key

**Choice:** `CRONBOX_MCP_API_KEY` env var, resolved against the `api_keys` table at startup.

**Why not JWT for MCP:** The MCP server runs as a subprocess (STDIO transport) or background service (HTTP transport). There's no interactive login flow. A pre-configured API key is simpler and appropriate for machine-to-machine auth.

### New Files

**Backend:**
- `src/cronbox/models/auth.py` — User, APIKey, RefreshToken SQLAlchemy models + password/key helpers
- `src/cronbox/api/permissions.py` — RBAC dependency factories
- `src/cronbox/api/routes_auth.py` — login, refresh, logout, me endpoints
- `src/cronbox/api/routes_keys.py` — API key CRUD endpoints
- `src/cronbox/api/routes_users.py` — admin user management endpoints
- `src/cronbox/cli.py` — CLI with create-user and serve subcommands

**Frontend:**
- `frontend/src/context/AuthContext.tsx` — auth state management
- `frontend/src/components/Login.tsx` — login page
- `frontend/src/components/ProtectedRoute.tsx` — auth gate wrapper
- `frontend/src/components/Settings.tsx` — API key management page
- `frontend/src/components/AdminUsers.tsx` — admin user management page

**Modified:**
- `src/cronbox/config.py` — jwt_secret, token expiry, mcp_api_key settings
- `src/cronbox/api/auth.py` — rewrite verify_api_key → get_current_user (JWT + API key + legacy)
- `src/cronbox/main.py` — wire new routers, import auth models, RBAC deps
- `src/cronbox/mcp/server.py` — API key auth + permission checks on mutating tools
- `frontend/src/api.ts` — auth headers, 401 handling, new API functions
- `frontend/src/App.tsx` — new routes, ProtectedRoute wrapper
- `frontend/src/components/Layout.tsx` — nav links, user info, logout
- `pyproject.toml` — new deps (passlib, pyjwt, python-multipart) + CLI entry point

---

## Open Questions / Future Considerations

- **Market calendar awareness**: Jobs run on weekday schedules, but markets also close on holidays. Could add a market calendar check (e.g., `exchange_calendars` library) that skips runs on market holidays. Not in v1.
- **Job dependencies**: No job-to-job dependency support in v1. If needed later, could add a `depends_on` field.
- **Config hot-reload via filesystem watcher**: v1 uses a manual `POST /api/config/reload` endpoint. Could add `watchfiles` to auto-detect YAML changes later.
- ~~**Authentication**: The web UI has no auth in v1. Fine for local/VPN access. Could add basic auth or API key later.~~ **Fully resolved**: Multi-user JWT auth + per-user API keys + 3-role RBAC (admin/operator/viewer). Frontend login page, API key management UI, admin user management. CLI bootstrap with `cronbox create-user`. Full backwards compatibility (empty jwt_secret = dev mode). See "Authentication System Design" section above.
- **WebSocket for live logs**: v1 polls for log content. Could upgrade to WebSocket streaming for real-time log following.
- **Log retention cleanup**: `CRONBOX_LOG_RETENTION_DAYS` is configured but the cleanup task is not yet implemented. Needs a periodic job that deletes log files older than the threshold.
- ~~**Tests**: No test suite yet. Priority areas: YAML loader validation, API route responses, runner step execution logic, Docker ops mocking.~~ **Resolved** (ac834ad): 72 tests added (52 backend, 20 frontend). Remaining gaps: runner, engine, database, runs routes, config, MCP server — placeholder files ready.
