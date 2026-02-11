import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from cronbox.api.permissions import require_admin, require_operator
from cronbox.executor.runner import execute_job
from cronbox.models.api_models import (
    ContainerInfo,
    CreateJobRequest,
    JobDetail,
    JobSummary,
    LastRunInfo,
    ReloadResponse,
    RunSummary,
    ScheduleInfo,
    StepInfo,
    TriggerResponse,
    UpdateJobRequest,
)
from cronbox.models.database import Job, JobRun
from cronbox.models.job_config import (
    ContainerConfig,
    JobConfig,
    NotifyConfig,
    ScheduleConfig,
    StepConfig,
)
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


def _request_to_job_config(name: str, body: CreateJobRequest | UpdateJobRequest, existing: JobConfig | None = None) -> JobConfig:
    """Convert an API request body to a JobConfig, merging with existing config for partial updates."""
    if isinstance(body, CreateJobRequest):
        return JobConfig(
            name=name,
            description=body.description,
            schedule=ScheduleConfig(**body.schedule.model_dump()),
            container=ContainerConfig(**body.container.model_dump()),
            steps=[StepConfig(**s.model_dump()) for s in body.steps],
            notify=NotifyConfig(**body.notify.model_dump()) if body.notify else None,
            timeout_seconds=body.timeout_seconds,
        )

    # UpdateJobRequest — merge with existing
    assert existing is not None
    return JobConfig(
        name=name,
        description=body.description if body.description is not None else existing.description,
        schedule=ScheduleConfig(**body.schedule.model_dump()) if body.schedule else existing.schedule,
        container=ContainerConfig(**body.container.model_dump()) if body.container else existing.container,
        steps=[StepConfig(**s.model_dump()) for s in body.steps] if body.steps else existing.steps,
        notify=NotifyConfig(**body.notify.model_dump()) if body.notify else existing.notify,
        timeout_seconds=body.timeout_seconds if body.timeout_seconds is not None else existing.timeout_seconds,
    )


def _validate_job_config(config: JobConfig):
    """Validate job config business rules beyond Pydantic schema validation."""
    # Validate cron expression has 5 fields
    parts = config.schedule.cron.split()
    if len(parts) != 5:
        raise HTTPException(status_code=400, detail="Cron expression must have exactly 5 fields")

    # Validate container mode
    if config.container.mode not in ("persistent", "ephemeral"):
        raise HTTPException(status_code=400, detail="Container mode must be 'persistent' or 'ephemeral'")

    # Validate container requirements
    if config.container.mode == "persistent" and not config.container.name:
        raise HTTPException(status_code=400, detail="Persistent container mode requires a container name")
    if config.container.mode == "ephemeral" and not config.container.image:
        raise HTTPException(status_code=400, detail="Ephemeral container mode requires an image")

    # Validate at least one step
    if not config.steps:
        raise HTTPException(status_code=400, detail="At least one step is required")

    # Validate job name (alphanumeric, hyphens, underscores)
    if not all(c.isalnum() or c in "-_" for c in config.name):
        raise HTTPException(status_code=400, detail="Job name must contain only alphanumeric characters, hyphens, and underscores")


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


@router.post("/jobs", dependencies=[Depends(require_admin)])
async def create_job(body: CreateJobRequest, request: Request):
    engine = request.app.state.scheduler_engine
    session_factory = request.app.state.session_factory

    config = _request_to_job_config(body.name, body)
    _validate_job_config(config)

    # Check for duplicate name
    if engine.get_config(body.name):
        raise HTTPException(status_code=409, detail=f"Job '{body.name}' already exists")

    # Persist to database
    async with session_factory() as session:
        job = Job(name=config.name, config_json=config.model_dump_json())
        session.add(job)
        await session.commit()

    # Register in scheduler
    from cronbox.main import _execute_job_wrapper

    settings = request.app.state.settings
    docker_ops = getattr(request.app.state, "docker_ops", None)
    await engine.register_job(
        config,
        _execute_job_wrapper,
        kwargs=dict(
            session_factory=session_factory,
            settings=settings,
            docker_ops=docker_ops,
        ),
    )

    return {"message": "Job created", "job_name": config.name}


@router.put("/jobs/{name}", dependencies=[Depends(require_admin)])
async def update_job(name: str, body: UpdateJobRequest, request: Request):
    engine = request.app.state.scheduler_engine
    session_factory = request.app.state.session_factory

    existing = engine.get_config(name)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Job '{name}' not found")

    config = _request_to_job_config(name, body, existing)
    _validate_job_config(config)

    # Update in database
    async with session_factory() as session:
        result = await session.execute(select(Job).where(Job.name == name))
        db_job = result.scalar_one_or_none()
        if not db_job:
            raise HTTPException(status_code=404, detail=f"Job '{name}' not found in database")
        db_job.config_json = config.model_dump_json()
        await session.commit()

    # Re-register in scheduler
    from cronbox.main import _execute_job_wrapper

    settings = request.app.state.settings
    docker_ops = getattr(request.app.state, "docker_ops", None)
    await engine.register_job(
        config,
        _execute_job_wrapper,
        kwargs=dict(
            session_factory=session_factory,
            settings=settings,
            docker_ops=docker_ops,
        ),
    )

    return {"message": "Job updated", "job_name": name}


@router.delete("/jobs/{name}", dependencies=[Depends(require_admin)])
async def delete_job(name: str, request: Request):
    engine = request.app.state.scheduler_engine
    session_factory = request.app.state.session_factory

    if not engine.get_config(name):
        raise HTTPException(status_code=404, detail=f"Job '{name}' not found")

    # Check if job is currently running
    existing_task = _running_tasks.get(name)
    if existing_task and not existing_task.done():
        raise HTTPException(status_code=409, detail=f"Job '{name}' is currently running")

    # Remove from database
    async with session_factory() as session:
        result = await session.execute(select(Job).where(Job.name == name))
        db_job = result.scalar_one_or_none()
        if db_job:
            await session.delete(db_job)
            await session.commit()

    # Remove from scheduler
    await engine.remove_job(name)

    return {"message": "Job deleted", "job_name": name}


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
    docker_ops = getattr(request.app.state, "docker_ops", None)

    async def run_in_background():
        async with session_factory() as session:
            await execute_job(config, "manual", db_session=session, settings=settings, docker_ops=docker_ops)

    task = asyncio.create_task(run_in_background())
    task.add_done_callback(lambda t: _task_done_callback(name, t))
    _running_tasks[name] = task

    return TriggerResponse(message="Job triggered", job_name=name)


@router.post("/config/reload", response_model=ReloadResponse, dependencies=[Depends(require_admin)])
async def reload_config(request: Request):
    settings = request.app.state.settings
    engine = request.app.state.scheduler_engine
    session_factory = request.app.state.session_factory

    configs = load_jobs(settings.jobs_config_dir)
    if not configs:
        return ReloadResponse(message="No YAML configs found to import", jobs_loaded=0)

    from cronbox.main import _execute_job_wrapper

    docker_ops = getattr(request.app.state, "docker_ops", None)
    imported = 0

    async with session_factory() as session:
        for config in configs:
            # Upsert: update if exists, insert if new
            result = await session.execute(select(Job).where(Job.name == config.name))
            db_job = result.scalar_one_or_none()
            if db_job:
                db_job.config_json = config.model_dump_json()
            else:
                session.add(Job(name=config.name, config_json=config.model_dump_json()))
            imported += 1

            # Register in scheduler
            await engine.register_job(
                config,
                _execute_job_wrapper,
                kwargs=dict(
                    session_factory=session_factory,
                    settings=settings,
                    docker_ops=docker_ops,
                ),
            )

        await session.commit()

    return ReloadResponse(message=f"Imported {imported} jobs from YAML", jobs_loaded=imported)
