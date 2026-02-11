from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from cronbox.models.database import JobRun
from cronbox.models.job_config import (
    ContainerConfig,
    JobConfig,
    ScheduleConfig,
    StepConfig,
)


def _make_job_config(name="test-job"):
    return JobConfig(
        name=name,
        description="Test job",
        schedule=ScheduleConfig(cron="0 * * * *", timezone="UTC", enabled=True),
        container=ContainerConfig(mode="persistent", name="test-ctr"),
        steps=[StepConfig(name="step-1", command="echo hello")],
    )


class TestListJobs:
    async def test_empty_list(self, async_client):
        resp = await async_client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_jobs(self, async_client):
        from cronbox.main import app

        config = _make_job_config()
        app.state.scheduler_engine.get_all_configs.return_value = [config]

        resp = await async_client.get("/api/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "test-job"
        assert data[0]["schedule"]["cron"] == "0 * * * *"

    async def test_list_with_last_run(self, async_client, db_engine, db_session_factory):
        from cronbox.main import app

        config = _make_job_config()
        app.state.scheduler_engine.get_all_configs.return_value = [config]

        async with db_session_factory() as session:
            run = JobRun(
                job_name="test-job",
                status="success",
                trigger="scheduled",
                started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                finished_at=datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc),
                duration_seconds=30.0,
            )
            session.add(run)
            await session.commit()

        resp = await async_client.get("/api/jobs")
        data = resp.json()
        assert data[0]["last_run"] is not None
        assert data[0]["last_run"]["status"] == "success"


class TestGetJob:
    async def test_get_existing_job(self, async_client):
        from cronbox.main import app

        config = _make_job_config()
        app.state.scheduler_engine.get_config.return_value = config

        resp = await async_client.get("/api/jobs/test-job")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-job"
        assert data["container"]["mode"] == "persistent"
        assert len(data["steps"]) == 1

    async def test_get_nonexistent_job(self, async_client):
        resp = await async_client.get("/api/jobs/no-such-job")
        assert resp.status_code == 404


class TestTriggerJob:
    async def test_trigger_existing_job(self, async_client):
        from cronbox.main import app

        config = _make_job_config()
        app.state.scheduler_engine.get_config.return_value = config

        resp = await async_client.post("/api/jobs/test-job/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_name"] == "test-job"
        assert "triggered" in data["message"].lower() or "trigger" in data["message"].lower()

    async def test_trigger_nonexistent_job(self, async_client):
        resp = await async_client.post("/api/jobs/no-such-job/trigger")
        assert resp.status_code == 404
