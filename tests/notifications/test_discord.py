from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cronbox.config import Settings
from cronbox.notifications.discord import send_failure_notification


def _make_run(**kwargs):
    defaults = dict(
        id=1,
        job_name="test-job",
        status="failed",
        trigger="scheduled",
        started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
        duration_seconds=60.0,
        log_file="logs/test-job/20240101_120000.log",
    )
    defaults.update(kwargs)
    run = MagicMock()
    for k, v in defaults.items():
        setattr(run, k, v)
    return run


class TestSendFailureNotification:
    async def test_no_webhook_url_returns_early(self):
        settings = Settings(discord_webhook_url="", web_base_url="")
        run = _make_run()

        with patch("cronbox.notifications.discord.httpx.AsyncClient") as mock_cls:
            await send_failure_notification("test-job", run, "step-1", settings)
            mock_cls.assert_not_called()

    async def test_sends_correct_embed(self):
        settings = Settings(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            web_base_url="",
        )
        run = _make_run()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("cronbox.notifications.discord.httpx.AsyncClient", return_value=mock_client):
            await send_failure_notification("test-job", run, "step-1", settings)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://discord.com/api/webhooks/123/abc"

        payload = call_args[1]["json"]
        embed = payload["embeds"][0]
        assert "Failed" in embed["title"]
        assert embed["color"] == 0xFF0000

        field_names = [f["name"] for f in embed["fields"]]
        assert "Job" in field_names
        assert "Failed Step" in field_names

    async def test_log_url_included_with_web_base_url(self):
        settings = Settings(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            web_base_url="https://cronbox.example.com",
        )
        run = _make_run(log_file="logs/test-job/20240101_120000.log")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("cronbox.notifications.discord.httpx.AsyncClient", return_value=mock_client):
            await send_failure_notification("test-job", run, "step-1", settings)

        payload = mock_client.post.call_args[1]["json"]
        fields = payload["embeds"][0]["fields"]
        log_field = next((f for f in fields if f["name"] == "Logs"), None)
        assert log_field is not None
        assert "cronbox.example.com" in log_field["value"]
        assert "20240101_120000.log" in log_field["value"]

    async def test_log_url_omitted_without_web_base_url(self):
        settings = Settings(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            web_base_url="",
        )
        run = _make_run(log_file="logs/test-job/20240101_120000.log")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("cronbox.notifications.discord.httpx.AsyncClient", return_value=mock_client):
            await send_failure_notification("test-job", run, "step-1", settings)

        payload = mock_client.post.call_args[1]["json"]
        fields = payload["embeds"][0]["fields"]
        log_field = next((f for f in fields if f["name"] == "Logs"), None)
        assert log_field is None
