from fastapi import APIRouter, HTTPException, Request

from cronbox.models.api_models import (
    PaginatedRuns,
    RunDetail,
    RunSummary,
    StepResultResponse,
)
from cronbox.models.database import JobRun

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/api")


@router.get("/runs", response_model=PaginatedRuns)
async def list_runs(
    request: Request,
    job_name: str | None = None,
    page: int = 1,
    per_page: int = 20,
):
    session_factory = request.app.state.session_factory
    offset = (page - 1) * per_page

    async with session_factory() as session:
        query = select(JobRun).order_by(JobRun.started_at.desc())
        count_query = select(func.count(JobRun.id))

        if job_name:
            query = query.where(JobRun.job_name == job_name)
            count_query = count_query.where(JobRun.job_name == job_name)

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        result = await session.execute(query.offset(offset).limit(per_page))
        runs = result.scalars().all()

    return PaginatedRuns(
        runs=[
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
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: int, request: Request):
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        result = await session.execute(
            select(JobRun)
            .where(JobRun.id == run_id)
            .options(selectinload(JobRun.step_results))
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return RunDetail(
        id=run.id,
        job_name=run.job_name,
        status=run.status,
        trigger=run.trigger,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=run.duration_seconds,
        log_file=run.log_file,
        steps=[
            StepResultResponse(
                name=s.step_name,
                status=s.status,
                exit_code=s.exit_code,
                duration_seconds=s.duration_seconds,
            )
            for s in run.step_results
        ],
    )
