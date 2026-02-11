from datetime import datetime, timezone

import pytest

from cronbox.models.database import JobRun


@pytest.mark.asyncio
class TestGetRun:
    async def test_get_run_strips_log_path(self, async_client, db_session_factory):
        """Verify log_file in response doesn't contain full server path."""
        async with db_session_factory() as session:
            run = JobRun(
                job_name="test-job",
                status="success",
                trigger="manual",
                started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                finished_at=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
                duration_seconds=60.0,
                log_file="logs/test-job/20240101_120000.log",
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        resp = await async_client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        # Should return relative path, not full path
        assert data["log_file"] == "test-job/20240101_120000.log"
        # Should NOT start with "logs/" or "/"
        assert not data["log_file"].startswith("logs/")
        assert not data["log_file"].startswith("/")

    async def test_get_run_strips_absolute_path(self, async_client, db_session_factory):
        """Verify absolute paths are also stripped to job_name/filename."""
        async with db_session_factory() as session:
            run = JobRun(
                job_name="test-job",
                status="success",
                trigger="manual",
                started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                finished_at=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
                duration_seconds=60.0,
                log_file="/home/user/cronbox/logs/test-job/20240101_120000.log",
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        resp = await async_client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["log_file"] == "test-job/20240101_120000.log"
        assert not data["log_file"].startswith("/")

    async def test_get_run_null_log_file(self, async_client, db_session_factory):
        """Verify null log_file is returned as null."""
        async with db_session_factory() as session:
            run = JobRun(
                job_name="test-job",
                status="success",
                trigger="manual",
                started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                finished_at=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
                duration_seconds=60.0,
                log_file=None,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        resp = await async_client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["log_file"] is None

    async def test_get_run_not_found(self, async_client):
        resp = await async_client.get("/api/runs/99999")
        assert resp.status_code == 404
