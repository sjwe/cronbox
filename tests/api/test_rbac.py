from unittest.mock import AsyncMock, MagicMock

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


class TestViewerPermissions:
    async def test_viewer_can_list_jobs(self, auth_async_client, viewer_user, viewer_token):
        resp = await auth_async_client.get(
            "/api/jobs",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 200

    async def test_viewer_cannot_trigger(self, auth_async_client, viewer_user, viewer_token):
        from cronbox.main import app

        config = _make_job_config()
        app.state.scheduler_engine.get_config.return_value = config

        resp = await auth_async_client.post(
            "/api/jobs/test-job/trigger",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_reload(self, auth_async_client, viewer_user, viewer_token):
        resp = await auth_async_client.post(
            "/api/config/reload",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403


class TestOperatorPermissions:
    async def test_operator_can_trigger(self, auth_async_client, operator_user, operator_token):
        from cronbox.api import routes_jobs
        from cronbox.main import app

        config = _make_job_config()
        app.state.scheduler_engine.get_config.return_value = config

        resp = await auth_async_client.post(
            "/api/jobs/test-job/trigger",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 200
        routes_jobs._running_tasks.clear()

    async def test_operator_cannot_reload(self, auth_async_client, operator_user, operator_token):
        resp = await auth_async_client.post(
            "/api/config/reload",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 403


class TestAdminPermissions:
    async def test_admin_can_reload(self, auth_async_client, admin_user, admin_token):
        from cronbox.main import app

        app.state.scheduler_engine.register_jobs = AsyncMock()

        resp = await auth_async_client.post(
            "/api/config/reload",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
