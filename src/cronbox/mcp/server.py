import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastmcp import FastMCP
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from cronbox.config import Settings
from cronbox.executor.runner import execute_job
from cronbox.models.database import JobRun, get_engine, get_session_factory, init_db
from cronbox.models.job_config import JobConfig
from cronbox.models.queries import get_latest_runs
from cronbox.scheduler.engine import SchedulerEngine
from cronbox.scheduler.loader import load_jobs
from cronbox.utils import read_log_tail

logger = logging.getLogger(__name__)

# Module-level state, initialized by lifespan
_settings: Settings | None = None
_session_factory = None
_engine: SchedulerEngine | None = None
_startup_time: datetime | None = None


@asynccontextmanager
async def app_lifespan(server):
    global _settings, _session_factory, _engine, _startup_time

    _settings = Settings()
    _startup_time = datetime.now(timezone.utc)

    await init_db(_settings.db_path)
    _session_factory = get_session_factory(_settings.db_path)

    _engine = SchedulerEngine()
    configs = load_jobs(_settings.jobs_config_dir)

    async def _execute_job_wrapper(job_config: JobConfig):
        async with _session_factory() as session:
            await execute_job(
                job_config, "scheduled", db_session=session, settings=_settings
            )

    await _engine.start()
    await _engine.register_jobs(configs, _execute_job_wrapper)
    logger.info("MCP server initialized with %d jobs", len(configs))

    try:
        yield
    finally:
        await _engine.stop()
        db_engine = get_engine(_settings.db_path)
        await db_engine.dispose()
        logger.info("MCP server shut down")


mcp = FastMCP(name="cronbox", lifespan=app_lifespan)


# --- Tools ---


@mcp.tool
async def list_jobs() -> str:
    """List all jobs with schedule, next run time, and last status."""
    configs = _engine.get_all_configs()

    next_run_times = await _engine.get_all_next_run_times()

    async with _session_factory() as session:
        latest_runs = await get_latest_runs(session)

    results = []
    for config in configs:
        next_run = next_run_times.get(config.name)
        last_run = latest_runs.get(config.name)

        results.append(
            {
                "name": config.name,
                "description": config.description,
                "cron": config.schedule.cron,
                "timezone": config.schedule.timezone,
                "enabled": config.schedule.enabled,
                "next_run": next_run.isoformat() if next_run else None,
                "last_status": last_run.status if last_run else None,
                "last_run_at": last_run.started_at.isoformat()
                if last_run
                else None,
            }
        )

    return json.dumps(results, indent=2)


@mcp.tool
async def get_job(job_name: str) -> str:
    """Get job configuration and last 10 runs for a specific job."""
    config = _engine.get_config(job_name)
    if not config:
        return json.dumps({"error": f"Job '{job_name}' not found"})

    next_run = await _engine.get_next_run_time(job_name)

    async with _session_factory() as session:
        result = await session.execute(
            select(JobRun)
            .where(JobRun.job_name == job_name)
            .order_by(JobRun.started_at.desc())
            .limit(10)
        )
        runs = result.scalars().all()

    return json.dumps(
        {
            "name": config.name,
            "description": config.description,
            "cron": config.schedule.cron,
            "timezone": config.schedule.timezone,
            "enabled": config.schedule.enabled,
            "container_mode": config.container.mode,
            "container_name": config.container.name,
            "next_run": next_run.isoformat() if next_run else None,
            "steps": [
                {
                    "name": s.name,
                    "command": s.command,
                    "timeout_seconds": s.timeout_seconds,
                }
                for s in config.steps
            ],
            "recent_runs": [
                {
                    "id": r.id,
                    "status": r.status,
                    "trigger": r.trigger,
                    "started_at": r.started_at.isoformat(),
                    "finished_at": r.finished_at.isoformat()
                    if r.finished_at
                    else None,
                    "duration_seconds": r.duration_seconds,
                }
                for r in runs
            ],
        },
        indent=2,
    )


@mcp.tool
async def trigger_job(job_name: str) -> str:
    """Trigger an immediate manual run of a job. Returns the run_id."""
    config = _engine.get_config(job_name)
    if not config:
        return json.dumps({"error": f"Job '{job_name}' not found"})

    async with _session_factory() as session:
        run = await execute_job(
            config, "manual", db_session=session, settings=_settings
        )

    return json.dumps(
        {"message": "Job triggered", "job_name": job_name, "run_id": run.id}
    )


@mcp.tool
async def list_runs(job_name: str | None = None, limit: int = 20) -> str:
    """List recent job runs, optionally filtered by job name."""
    async with _session_factory() as session:
        query = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
        if job_name:
            query = query.where(JobRun.job_name == job_name)

        result = await session.execute(query)
        runs = result.scalars().all()

    return json.dumps(
        [
            {
                "id": r.id,
                "job_name": r.job_name,
                "status": r.status,
                "trigger": r.trigger,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat()
                if r.finished_at
                else None,
                "duration_seconds": r.duration_seconds,
            }
            for r in runs
        ],
        indent=2,
    )


@mcp.tool
async def get_run(run_id: int) -> str:
    """Get detailed information about a specific run, including per-step results."""
    async with _session_factory() as session:
        result = await session.execute(
            select(JobRun)
            .where(JobRun.id == run_id)
            .options(selectinload(JobRun.step_results))
        )
        run = result.scalar_one_or_none()

    if not run:
        return json.dumps({"error": f"Run {run_id} not found"})

    return json.dumps(
        {
            "id": run.id,
            "job_name": run.job_name,
            "status": run.status,
            "trigger": run.trigger,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat()
            if run.finished_at
            else None,
            "duration_seconds": run.duration_seconds,
            "log_file": run.log_file,
            "step_results": [
                {
                    "step_name": s.step_name,
                    "status": s.status,
                    "exit_code": s.exit_code,
                    "started_at": s.started_at.isoformat(),
                    "finished_at": s.finished_at.isoformat()
                    if s.finished_at
                    else None,
                    "duration_seconds": s.duration_seconds,
                    "output_snippet": s.output_snippet,
                }
                for s in run.step_results
            ],
        },
        indent=2,
    )


@mcp.tool
async def get_log(job_name: str, run_id: int | None = None) -> str:
    """Get log content for a job. Returns the latest log if run_id is omitted."""
    if run_id is not None:
        async with _session_factory() as session:
            result = await session.execute(
                select(JobRun).where(JobRun.id == run_id)
            )
            run = result.scalar_one_or_none()

        if not run or not run.log_file:
            return json.dumps({"error": f"No log found for run {run_id}"})

        log_path = Path(run.log_file)
        # Prevent path traversal from DB-stored paths
        resolved = log_path.resolve()
        base = Path(_settings.logs_dir).resolve()
        if not str(resolved).startswith(str(base)):
            return json.dumps({"error": "Access denied"})
    else:
        log_dir = Path(_settings.logs_dir) / job_name
        # Prevent path traversal from user input
        resolved_dir = log_dir.resolve()
        base = Path(_settings.logs_dir).resolve()
        if not str(resolved_dir).startswith(str(base)):
            return json.dumps({"error": "Access denied"})
        if not log_dir.exists():
            return json.dumps(
                {"error": f"No logs found for job '{job_name}'"}
            )

        log_files = sorted(
            (f for f in log_dir.iterdir() if f.is_file() and f.suffix == ".log"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not log_files:
            return json.dumps(
                {"error": f"No log files found for job '{job_name}'"}
            )

        log_path = log_files[0]

    if not log_path.exists():
        return json.dumps({"error": "Log file not found"})

    content = read_log_tail(log_path)
    return content


@mcp.tool
async def reload_config() -> str:
    """Hot-reload YAML job configs into the scheduler."""
    configs = load_jobs(_settings.jobs_config_dir)

    async def _execute_job_wrapper(job_config: JobConfig):
        async with _session_factory() as session:
            await execute_job(
                job_config, "scheduled", db_session=session, settings=_settings
            )

    await _engine.register_jobs(configs, _execute_job_wrapper)
    return json.dumps(
        {"message": "Configuration reloaded", "jobs_loaded": len(configs)}
    )


# --- Resources ---


@mcp.resource("cronbox://jobs")
async def resource_all_jobs() -> str:
    """All job configurations as JSON."""
    configs = _engine.get_all_configs()
    return json.dumps(
        [config.model_dump(mode="json") for config in configs],
        indent=2,
    )


@mcp.resource("cronbox://jobs/{name}")
async def resource_job_config(name: str) -> str:
    """Single job configuration as YAML."""
    config = _engine.get_config(name)
    if not config:
        return f"# Job '{name}' not found"
    return yaml.dump(config.model_dump(mode="json"), default_flow_style=False)


@mcp.resource("cronbox://status")
async def resource_status() -> str:
    """System status: uptime, total jobs, running jobs, recent failures."""
    configs = _engine.get_all_configs()
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _startup_time).total_seconds()

    async with _session_factory() as session:
        running_result = await session.execute(
            select(func.count(JobRun.id)).where(JobRun.status == "running")
        )
        running_count = running_result.scalar() or 0

        failures_result = await session.execute(
            select(JobRun)
            .where(JobRun.status == "failed")
            .order_by(JobRun.started_at.desc())
            .limit(5)
        )
        recent_failures = failures_result.scalars().all()

    return json.dumps(
        {
            "uptime_seconds": round(uptime_seconds),
            "total_jobs": len(configs),
            "running_jobs": running_count,
            "recent_failures": [
                {
                    "job_name": f.job_name,
                    "started_at": f.started_at.isoformat(),
                    "finished_at": f.finished_at.isoformat()
                    if f.finished_at
                    else None,
                }
                for f in recent_failures
            ],
        },
        indent=2,
    )
