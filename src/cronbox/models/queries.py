from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cronbox.models.database import JobRun


async def get_latest_runs(session: AsyncSession) -> dict[str, JobRun]:
    """Get the latest run for each job in a single query."""
    subq = (
        select(
            JobRun.id,
            func.row_number()
            .over(
                partition_by=JobRun.job_name,
                order_by=JobRun.started_at.desc(),
            )
            .label("rn"),
        ).subquery()
    )

    result = await session.execute(
        select(JobRun).join(subq, JobRun.id == subq.c.id).where(subq.c.rn == 1)
    )
    runs = result.scalars().all()
    return {r.job_name: r for r in runs}
