# Code Review Log

## Review: 2026-02-11

**Scope:** Full codebase (`src/cronbox/`, `frontend/src/`)
**Files scanned:** 32 (23 Python + 9 TypeScript)
**Areas:** Security, Performance, Test Coverage
**Total findings:** 32 (6 critical, 13 high, 12 medium, 1 low)

### Summary

| Area | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Security | 0 | 3 | 3 | 1 | 7 |
| Performance | 0 | 4 | 6 | 0 | 10 |
| Test Coverage | 6 | 6 | 3 | 0 | 15 |
| **Total** | **6** | **13** | **12** | **1** | **32** |

---

## Security Findings

### ~~HIGH: No authentication on any endpoint~~ — FIXED (pending commit)
- **File:** `src/cronbox/main.py:57-65`
- **Issue:** The entire API is unauthenticated. Anyone who can reach the server can trigger Docker job execution, read all logs, and reload configuration.
- **Fix:** New `api/auth.py` with API key middleware (`X-API-Key` or `Bearer` header). Applied to all API routes via `Depends()`. Default `api_key=""` means no auth for local dev. 6 tests added.

### ~~HIGH: Path traversal in list_logs~~ — FIXED (a2faac1)
- **File:** `src/cronbox/api/routes_logs.py:12-18`
- **Issue:** `list_logs` constructs a directory path from user-controlled `job_name` with no traversal protection. `GET /api/logs/../../etc` lists files outside the logs directory. The sibling `get_log` endpoint correctly uses `resolve()+startswith()` — this one does not.
- **Fix:** Added `resolve()+startswith()` guard to `list_logs`. Two traversal tests added.

### ~~HIGH: Path traversal in MCP get_log~~ — FIXED (a2faac1)
- **File:** `src/cronbox/mcp/server.py:249-284`
- **Issue:** Two vulnerable paths: (1) `log_path` read directly from DB with no validation, (2) `job_name` from MCP input joined into path with no traversal check. Both allow arbitrary file reads.
- **Fix:** Added `resolve()+startswith()` validation on both DB-stored and user-supplied paths.

### ~~MEDIUM: Default bind on 0.0.0.0~~ — FIXED (pending commit)
- **File:** `src/cronbox/config.py:12`
- **Issue:** API binds to all interfaces by default. Combined with no auth, this exposes the full API to the local network.
- **Fix:** Default changed to `127.0.0.1`.

### ~~MEDIUM: Server filesystem paths leaked in API responses~~ — FIXED (pending commit)
- **File:** `src/cronbox/api/routes_runs.py:83`, `src/cronbox/mcp/server.py:228`
- **Issue:** Full server-side log file paths exposed to API consumers, leaking internal directory structure.
- **Fix:** `log_file` stripped to `job_name/filename` in both API and MCP responses. 4 tests added.

### MEDIUM: Alpha pre-release dependency
- **File:** `pyproject.toml:8`
- **Issue:** `apscheduler>=4.0.0a1` — alpha software in production. May contain undiscovered bugs and breaking changes.
- **Recommendation:** Pin to a tested version rather than open-ended `>=`.

### ~~LOW: Filesystem paths in MCP error messages~~ — FIXED (a2faac1)
- **File:** `src/cronbox/mcp/server.py:282`
- **Issue:** Error messages expose absolute paths to MCP clients.
- **Fix:** Changed to generic "Log file not found" error without path.

### Clean areas
- No hardcoded secrets — all config via pydantic-settings env vars
- No SQL injection — SQLAlchemy ORM with parameterized queries throughout
- No command injection — no eval/exec/subprocess/os.system
- YAML uses `safe_load` correctly
- React auto-escapes output, no `dangerouslySetInnerHTML`
- No SSRF — only outbound HTTP is Discord webhook from env config
- CORS defaults to same-origin (restrictive)

---

## Performance Findings

### ~~HIGH: N+1 queries in list_jobs (API)~~ — FIXED (a2faac1)
- **File:** `src/cronbox/api/routes_jobs.py:32-42`
- **Issue:** For each job, opens a new DB session and queries for its last run. With 50 jobs = 50 separate DB connections + queries per dashboard load.
- **Fix:** New `models/queries.py` with `get_latest_runs()` using `ROW_NUMBER()` window function. Single session, single query.

### ~~HIGH: N+1 queries in list_jobs (MCP)~~ — FIXED (a2faac1)
- **File:** `src/cronbox/mcp/server.py:72-82`
- **Issue:** Identical N+1 pattern duplicated in the MCP server.
- **Fix:** Both API and MCP now use shared `get_latest_runs()` helper.

### ~~HIGH: Unbounded log file read (MCP)~~ — FIXED (a2faac1)
- **File:** `src/cronbox/mcp/server.py:284`
- **Issue:** Reads entire log file into memory with no size limit. A 500MB log = 500MB+ memory.
- **Fix:** New `utils.py` with `read_log_tail(max_bytes=1MB)` — seeks to tail of large files.

### ~~HIGH: Unbounded log file read (API)~~ — FIXED (a2faac1)
- **File:** `src/cronbox/api/routes_logs.py:49`
- **Issue:** Same unbounded read in the REST API, returned as `PlainTextResponse`.
- **Fix:** Uses same `read_log_tail()` helper. 4 tests added (truncation + pagination).

### ~~MEDIUM: O(n^2) schedule lookup~~ — FIXED (a2faac1)
- **File:** `src/cronbox/scheduler/engine.py:51-56`
- **Issue:** `get_next_run_time` fetches ALL schedules then linear scans. Called in a loop from list_jobs, total is O(n^2).
- **Fix:** `get_next_run_time` now uses direct `get_schedule(id)`. New `get_all_next_run_times()` batch method used by `list_jobs`.

### MEDIUM: New Docker client per job execution
- **File:** `src/cronbox/executor/runner.py:40`
- **Issue:** `DockerOperations()` creates a new `docker.from_env()` connection per job execution.
- **Recommendation:** Share a singleton Docker client. It's thread-safe and designed for reuse.

### MEDIUM: Redundant container lookups
- **File:** `src/cronbox/executor/docker_ops.py:8-22`
- **Issue:** In persistent mode, each step calls `containers.get()` twice (once in `ensure_started`, once in `exec_in_container`).
- **Recommendation:** Cache container object or pass it between calls.

### ~~MEDIUM: Unpaginated log file listing~~ — FIXED (a2faac1)
- **File:** `src/cronbox/api/routes_logs.py:21-30`
- **Issue:** Lists all files in a log directory, stats each one, no pagination. Grows unbounded over time.
- **Fix:** Added `?limit=N` query param (default 100).

### MEDIUM: Un-virtualized log rendering in frontend
- **File:** `frontend/src/components/LogViewer.tsx:76-79`
- **Issue:** Creates a DOM element per log line on every render. 10,000 lines = 10,000 DOM nodes.
- **Recommendation:** Use `react-window` or `@tanstack/virtual` for virtualized rendering.

### ~~MEDIUM: Untracked background tasks~~ — FIXED (pending commit)
- **File:** `src/cronbox/api/routes_jobs.py:144`
- **Issue:** `asyncio.create_task()` with no stored reference and no concurrency guard. Exceptions silently swallowed.
- **Fix:** Task refs tracked in `_running_tasks` dict. Done callback logs errors. 409 Conflict on duplicate trigger. 2 tests added.

---

## Test Coverage Findings

> **RESOLVED (ac834ad):** Test infrastructure added and 72 tests written. See remediation details below.

~~**The project has zero test files and zero test infrastructure.** No pytest, no vitest, no test configuration of any kind.~~

### CRITICAL: Untested core modules

| File | What's Untested | Status |
|------|-----------------|--------|
| `executor/runner.py:17` | Job execution engine — Docker orchestration, step sequencing, timeouts, failure cascading, notifications | Placeholder |
| `executor/docker_ops.py:4` | All Docker operations — start, exec, ephemeral runs, output demuxing | **9 tests added** |
| `scheduler/engine.py:10` | Cron scheduling — fragile 5-part cron parsing, APScheduler lifecycle | Placeholder |
| `scheduler/loader.py:8` | YAML config loading — missing validation for invalid YAML, empty files, missing fields | **8 tests added** |
| `api/routes_jobs.py` | 4 endpoints including trigger (executes Docker) and reload (modifies scheduler) | **9 tests added** |
| `api/routes_runs.py` | Run listing with pagination and filtering | **4 tests added** |

### HIGH: Untested security-critical and integration modules

| File | What's Untested | Status |
|------|-----------------|--------|
| `api/routes_logs.py` | Path traversal guard is security-critical with zero tests | **12 tests added (traversal + truncation + pagination)** |
| `mcp/server.py` | 7 MCP tools + 3 resources | Placeholder |
| `notifications/discord.py` | Webhook payload construction, HTTP error handling | **4 tests added** |
| `models/database.py` | Schema creation, ORM relationships, session lifecycle | Placeholder |
| `models/job_config.py` | Pydantic validation, defaults, required fields | **18 tests added** |
| `config.py` | Environment variable loading with CRONBOX_ prefix | Placeholder |

### MEDIUM: Untested frontend logic

| File | What's Untested | Status |
|------|-----------------|--------|
| `frontend/src/api.ts` | 7 API client functions, error handling | **6 tests added** |
| `frontend/src/components/JobList.tsx:8` | `parseCronSchedule` and `relativeTime` pure functions | **7 tests added** |
| `frontend/src/components/LogViewer.tsx:10` | `highlightLine` branching logic | **7 tests added** |

### Infrastructure — DONE

**Python backend:**
- ~~Add `pytest`, `pytest-asyncio`, `httpx`, `pytest-cov` to dev dependencies~~ Done
- ~~Create `conftest.py` with async fixtures, in-memory SQLite, mock Docker client~~ Done (7 fixtures)
- ~~Create `tests/` directory mirroring `src/cronbox/`~~ Done

**TypeScript frontend:**
- ~~Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` to devDependencies~~ Done
- ~~Add vitest config to `vite.config.ts`~~ Done

### Remaining gaps

Placeholder test files exist for these modules — can be filled incrementally:
- `tests/executor/test_runner.py` — job execution engine (step sequencing, timeouts, failure cascading)
- `tests/scheduler/test_engine.py` — APScheduler lifecycle, cron registration
- `tests/models/test_database.py` — ORM relationships, schema creation
- ~~`tests/api/test_routes_runs.py` — pagination, filtering~~ **4 tests added** (path stripping, absolute paths, null log_file, 404)
- `tests/test_config.py` — env var loading
- `tests/mcp/test_server.py` — MCP tools and resources

---

## Top 5 Recommendations by Impact

1. ~~**Add authentication**~~ — **DONE** (pending commit). API key middleware + default bind changed to `127.0.0.1`. → [#2](https://github.com/sjwe/cronbox/issues/2) (closed)
2. ~~**Fix path traversal in `list_logs` and MCP `get_log`**~~ — **DONE** (a2faac1). Added `resolve()+startswith()` guards + 2 traversal tests. → [#1](https://github.com/sjwe/cronbox/issues/1) (closed)
3. ~~**Add test infrastructure and critical path tests**~~ — **DONE** (ac834ad). 72 tests across 9 files. → [#5](https://github.com/sjwe/cronbox/issues/5) (closed)
4. ~~**Batch the N+1 queries in `list_jobs`**~~ — **DONE** (a2faac1). Window function batch query + `get_all_next_run_times()`. → [#3](https://github.com/sjwe/cronbox/issues/3) (closed)
5. ~~**Add size limits to log file reads**~~ — **DONE** (a2faac1). `read_log_tail()` caps at 1MB + pagination. → [#4](https://github.com/sjwe/cronbox/issues/4) (closed)

### All issues

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| [#1](https://github.com/sjwe/cronbox/issues/1) | Fix path traversal vulnerabilities | High | **Closed** (a2faac1) |
| [#2](https://github.com/sjwe/cronbox/issues/2) | Add API authentication | High | **Closed** |
| [#3](https://github.com/sjwe/cronbox/issues/3) | Fix N+1 queries in list_jobs | High | **Closed** (a2faac1) |
| [#4](https://github.com/sjwe/cronbox/issues/4) | Add size limits to log file reads | High | **Closed** (a2faac1) |
| [#5](https://github.com/sjwe/cronbox/issues/5) | Add test infrastructure and critical path tests | Critical | **Closed** (ac834ad) |
| [#6](https://github.com/sjwe/cronbox/issues/6) | Reduce Docker client overhead | Medium | Open |
| [#7](https://github.com/sjwe/cronbox/issues/7) | Harden fire-and-forget background task | Medium | **Closed** |
| [#8](https://github.com/sjwe/cronbox/issues/8) | Virtualize LogViewer for large logs | Medium | Open |
| [#9](https://github.com/sjwe/cronbox/issues/9) | Stop leaking filesystem paths in API responses | Medium | **Closed** |
| [#10](https://github.com/sjwe/cronbox/issues/10) | Pin APScheduler to a tested version | Medium | Open |
| [#11](https://github.com/sjwe/cronbox/issues/11) | Add multi-user auth: JWT, per-user API keys, RBAC | High | **Closed** |
