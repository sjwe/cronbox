import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from cronbox.api.routes_jobs import router as jobs_router
from cronbox.api.routes_logs import router as logs_router
from cronbox.api.routes_runs import router as runs_router
from cronbox.config import Settings
from cronbox.executor.runner import execute_job
from cronbox.models.database import get_engine, get_session_factory, init_db
from cronbox.scheduler.engine import SchedulerEngine
from cronbox.scheduler.loader import load_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings

    # Init database
    await init_db(settings.db_path)
    app.state.session_factory = get_session_factory(settings.db_path)

    # Load job configs
    configs = load_jobs(settings.jobs_config_dir)
    logger.info("Loaded %d job configs", len(configs))

    # Start scheduler
    engine = SchedulerEngine()
    app.state.scheduler_engine = engine

    async def _execute_job_wrapper(job_config):
        async with app.state.session_factory() as session:
            await execute_job(
                job_config, "scheduled", db_session=session, settings=settings
            )

    await engine.start()
    await engine.register_jobs(configs, _execute_job_wrapper)
    logger.info("Scheduler started")

    yield

    await engine.stop()
    logger.info("Scheduler stopped")

    db_engine = get_engine(settings.db_path)
    await db_engine.dispose()


app = FastAPI(title="cronbox", version="0.1.0", lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(runs_router)
app.include_router(logs_router)

# Mount frontend static files if the dist directory exists
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
