from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import cronbox.models.database as db_module
from cronbox.config import Settings
from cronbox.models.database import Base
from cronbox.models.job_config import (
    ContainerConfig,
    JobConfig,
    ScheduleConfig,
    StepConfig,
)


@pytest.fixture
def settings(tmp_path):
    """Settings with test defaults: in-memory SQLite, temp dirs."""
    return Settings(
        db_path=":memory:",
        jobs_config_dir=str(tmp_path / "jobs"),
        logs_dir=str(tmp_path / "logs"),
        discord_webhook_url="",
        web_base_url="",
    )


@pytest.fixture
async def db_engine():
    """Async SQLAlchemy engine backed by in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine):
    """Async session factory bound to the in-memory engine."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(db_engine, db_session_factory):
    """Create tables, yield a session, then drop tables."""
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with db_session_factory() as session:
        yield session

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_docker():
    """Mock DockerOperations so tests never touch a real Docker daemon."""
    mock = MagicMock()
    mock.ensure_started = MagicMock()
    mock.exec_in_container = MagicMock(return_value=(0, "ok"))
    mock.run_ephemeral = MagicMock(return_value=(0, "ok"))
    mock.close = MagicMock()
    return mock


@pytest.fixture
async def async_client(db_engine, db_session_factory, settings):
    """
    httpx AsyncClient wired to the FastAPI app with test overrides.

    Bypasses the normal lifespan (which would start the real scheduler and
    connect to a real DB) and instead injects test fixtures into app.state.
    """
    # Reset the database module globals so the app doesn't use stale singletons
    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = db_engine
    db_module._session_factory = db_session_factory

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from cronbox.main import app

    # Inject test state — mirrors what lifespan() normally does
    app.state.settings = settings
    app.state.session_factory = db_session_factory

    # Provide a mock scheduler engine with sensible defaults
    mock_engine = MagicMock()
    mock_engine.get_all_configs.return_value = []
    mock_engine.get_config.return_value = None
    mock_engine.get_next_run_time = AsyncMock(return_value=None)
    app.state.scheduler_engine = mock_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Restore globals
    db_module._engine = original_engine
    db_module._session_factory = original_factory


@pytest.fixture
def sample_job_config():
    """A minimal JobConfig for use in tests."""
    return JobConfig(
        name="test-job",
        description="A test job",
        schedule=ScheduleConfig(cron="0 * * * *", timezone="UTC", enabled=True),
        container=ContainerConfig(mode="persistent", name="test-container"),
        steps=[
            StepConfig(name="step-1", command="echo hello"),
            StepConfig(name="step-2", command="echo world"),
        ],
        timeout_seconds=60,
    )
