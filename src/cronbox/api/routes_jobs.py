import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from cronbox.api.permissions import require_admin, require_operator
from cronbox.executor.runner import execute_job
from cronbox.models.api_models import (
    ContainerInfo,
    JobDetail,
    JobSummary,
    LastRunInfo,
    ReloadResponse,
    RunSummary,
    ScheduleInfo,
    StepInfo,
    TriggerResponse,
)
from cronbox.models.database import JobRun
from cronbox.models.queries import get_latest_runs
from cronbox.scheduler.loader import load_jobs

from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Track running background tasks by job name
_running_tasks: dict[str, asyncio.Task] = {}


def _task_done_callback(job_name: str, task: asyncio.Task):
    _running_tasks.pop(job_name, None)
    if task.cancelled():
        logger.warning("Job '%s' task was cancelled", job_name)
    elif exc := task.exception():
        logger.error("Job '%s' failed with exception: %s", job_name, exc, exc_info=exc)


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(request: Request):
    engine = request.app.state.scheduler_engine
    configs = engine.get_all_configs()
    session_factory = request.app.state.session_factory

    next_run_times = await engine.get_all_next_run_times()

    async with session_factory() as session:
        latest_runs = await get_latest_runs(session)

    summaries = []
    for config in configs:
        next_run = next_run_times.get(config.name)
        last_run_row = latest_runs.get(config.name)

        last_run = None
        if last_run_row:
            last_run = LastRunInfo(
                status=last_run_row.status,
                started_at=last_run_row.started_at,
                duration_seconds=last_run_row.duration_seconds,
            )

        summaries.append(
            JobSummary(
                name=config.name,
                description=config.description,
                schedule=ScheduleInfo(
                    cron=config.schedule.cron,
                    timezone=config.schedule.timezone,
                    enabled=config.schedule.enabled,
                ),
                next_run_time=next_run.isoformat() if next_run else None,
                last_run=last_run,
            )
        )

    return summaries


@router.get("/jobs/{name}", response_model=JobDetail)
async def get_job(name: str, request: Request):
    engine = request.app.state.scheduler_engine
    config = engine.get_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Job '{name}' not found")

    next_run = await engine.get_next_run_time(name)
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        result = await session.execute(
            select(JobRun)
            .where(JobRun.job_name == name)
            .order_by(JobRun.started_at.desc())
            .limit(50)
        )
        runs = result.scalars().all()

    last_run = None
    if runs:
        last_run = LastRunInfo(
            status=runs[0].status,
            started_at=runs[0].started_at,
            duration_seconds=runs[0].duration_seconds,
        )

    return JobDetail(
        name=config.name,
        description=config.description,
        schedule=ScheduleInfo(
            cron=config.schedule.cron,
            timezone=config.schedule.timezone,
            enabled=config.schedule.enabled,
        ),
        next_run_time=next_run.isoformat() if next_run else None,
        last_run=last_run,
        container=ContainerInfo(
            mode=config.container.mode,
            name=config.container.name,
            image=config.container.image,
        ),
        steps=[
            StepInfo(name=s.name, command=s.command, timeout_seconds=s.timeout_seconds)
            for s in config.steps
        ],
        recent_runs=[
            RunSummary(
                id=r.id,
                job_name=r.job_name,
                status=r.status,
                trigger=r.trigger,
                started_at=r.started_at,
                finished_at=r.finished_at,
                duration_seconds=r.duration_seconds,
            )
            for r in runs
        ],
    )


@router.post("/jobs/{name}/trigger", response_model=TriggerResponse, dependencies=[Depends(require_operator)])
async def trigger_job(name: str, request: Request):
    engine = request.app.state.scheduler_engine
    config = engine.get_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Job '{name}' not found")

    # Concurrency guard: prevent duplicate simultaneous runs
    existing_task = _running_tasks.get(name)
    if existing_task and not existing_task.done():
        raise HTTPException(status_code=409, detail=f"Job '{name}' is already running")

    settings = request.app.state.settings
    session_factory = request.app.state.session_factory

    async def run_in_background():
        async with session_factory() as session:
            await execute_job(config, "manual", db_session=session, settings=settings)

    task = asyncio.create_task(run_in_background())
    task.add_done_callback(lambda t: _task_done_callback(name, t))
    _running_tasks[name] = task

    return TriggerResponse(message="Job triggered", job_name=name)


@router.post("/config/reload", response_model=ReloadResponse, dependencies=[Depends(require_admin)])
async def reload_config(request: Request):
    settings = request.app.state.settings
    engine = request.app.state.scheduler_engine

    configs = load_jobs(settings.jobs_config_dir)

    async def _execute_job_wrapper(job_config):
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await execute_job(job_config, "scheduled", db_session=session, settings=settings)

    await engine.register_jobs(configs, _execute_job_wrapper)

    return ReloadResponse(message="Configuration reloaded", jobs_loaded=len(configs))
