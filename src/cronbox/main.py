import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from cronbox.api.auth import get_current_user
from cronbox.api.permissions import require_admin, require_operator
from cronbox.api.routes_auth import router as auth_router
from cronbox.api.routes_jobs import router as jobs_router
from cronbox.api.routes_keys import router as keys_router
from cronbox.api.routes_logs import router as logs_router
from cronbox.api.routes_runs import router as runs_router
from cronbox.api.routes_users import router as users_router
from cronbox.config import Settings
from cronbox.executor.docker_ops import DockerOperations
from cronbox.executor.runner import execute_job
import cronbox.models.auth  # noqa: F401 — register auth tables
from cronbox.models.database import Job, get_engine, get_session_factory, init_db
from cronbox.models.job_config import JobConfig
from cronbox.scheduler.engine import SchedulerEngine
from cronbox.scheduler.loader import load_jobs

from sqlalchemy import func, select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _execute_job_wrapper(job_config, *, session_factory, settings, docker_ops):
    async with session_factory() as session:
        await execute_job(
            job_config,
            "scheduled",
            db_session=session,
            settings=settings,
            docker_ops=docker_ops,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings

    # Init database
    await init_db(settings.db_path)
    app.state.session_factory = get_session_factory(settings.db_path)

    # Load job configs from database, seed from YAML if DB is empty
    async with app.state.session_factory() as session:
        count_result = await session.execute(select(func.count(Job.id)))
        job_count = count_result.scalar() or 0

        if job_count == 0:
            # Seed from YAML files on first run
            yaml_configs = load_jobs(settings.jobs_config_dir)
            if yaml_configs:
                for config in yaml_configs:
                    session.add(Job(name=config.name, config_json=config.model_dump_json()))
                await session.commit()
                logger.info("Seeded %d jobs from YAML files into database", len(yaml_configs))

        # Load all jobs from database
        result = await session.execute(select(Job))
        db_jobs = result.scalars().all()

    configs = [JobConfig.model_validate_json(j.config_json) for j in db_jobs]
    logger.info("Loaded %d job configs from database", len(configs))

    # Shared Docker client (singleton for the app lifetime)
    docker_ops = DockerOperations()
    app.state.docker_ops = docker_ops

    # Start scheduler
    engine = SchedulerEngine()
    app.state.scheduler_engine = engine

    await engine.start()
    await engine.register_jobs(
        configs,
        _execute_job_wrapper,
        kwargs=dict(
            session_factory=app.state.session_factory,
            settings=settings,
            docker_ops=docker_ops,
        ),
    )
    logger.info("Scheduler started")

    yield

    await engine.stop()
    logger.info("Scheduler stopped")

    docker_ops.close()

    db_engine = get_engine(settings.db_path)
    await db_engine.dispose()


app = FastAPI(title="cronbox", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(jobs_router, dependencies=[Depends(get_current_user)])
app.include_router(runs_router, dependencies=[Depends(get_current_user)])
app.include_router(logs_router, dependencies=[Depends(get_current_user)])
app.include_router(keys_router, dependencies=[Depends(get_current_user)])
app.include_router(users_router, dependencies=[Depends(get_current_user)])

# Mount frontend static files if the dist directory exists
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
