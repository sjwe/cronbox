from pathlib import Path

import pytest


class TestListLogs:
    async def test_list_logs_with_files(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "test-job"
        log_dir.mkdir(parents=True)
        (log_dir / "20240101_120000.log").write_text("log content 1")
        (log_dir / "20240102_120000.log").write_text("log content 2 longer")

        resp = await async_client.get("/api/logs/test-job")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["filename"] == "20240102_120000.log"
        assert data[1]["filename"] == "20240101_120000.log"
        assert all("size_bytes" in entry for entry in data)
        assert all("modified_at" in entry for entry in data)

    async def test_list_logs_nonexistent_job(self, async_client):
        resp = await async_client.get("/api/logs/no-such-job")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_logs_ignores_non_log_files(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "mixed-job"
        log_dir.mkdir(parents=True)
        (log_dir / "run.log").write_text("log data")
        (log_dir / "notes.txt").write_text("not a log")

        resp = await async_client.get("/api/logs/mixed-job")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["filename"] == "run.log"


    async def test_list_logs_path_traversal_blocked(self, async_client, settings):
        # Create a file outside logs dir
        secret_dir = Path(settings.logs_dir).parent / "secret-job"
        secret_dir.mkdir(parents=True)
        (secret_dir / "secret.log").write_text("sensitive")

        resp = await async_client.get("/api/logs/../secret-job")
        # Framework may normalize the path (404) or our guard catches it (403)
        # Either way, sensitive data must not be returned
        assert resp.status_code in (200, 403, 404)
        assert "sensitive" not in resp.text
        if resp.status_code == 200:
            assert resp.json() == []

    async def test_list_logs_path_traversal_encoded(self, async_client, settings):
        # Test with a job_name containing traversal that resolves outside logs dir
        secret_dir = Path(settings.logs_dir).parent / "secret-job2"
        secret_dir.mkdir(parents=True)
        (secret_dir / "secret.log").write_text("sensitive")

        resp = await async_client.get("/api/logs/..%2Fsecret-job2")
        assert resp.status_code in (200, 403, 404)
        assert "sensitive" not in resp.text
        if resp.status_code == 200:
            assert resp.json() == []


class TestGetLog:
    async def test_get_log_valid(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "test-job"
        log_dir.mkdir(parents=True)
        (log_dir / "run.log").write_text("line1\nline2\n")

        resp = await async_client.get("/api/logs/test-job/run.log")
        assert resp.status_code == 200
        assert "line1" in resp.text
        assert "line2" in resp.text

    async def test_get_log_not_found(self, async_client):
        resp = await async_client.get("/api/logs/test-job/missing.log")
        assert resp.status_code == 404

    async def test_path_traversal_blocked(self, async_client, settings):
        # Create a file outside the logs dir that an attacker might try to read
        secret = Path(settings.logs_dir).parent / "secret.txt"
        secret.write_text("sensitive data")

        resp = await async_client.get("/api/logs/test-job/../../secret.txt")
        # Should be either 403 (path traversal guard) or 404 (not found),
        # but never 200 with the file contents
        assert resp.status_code in (403, 404, 422)
        assert "sensitive data" not in resp.text


class TestGetLogSizeLimits:
    async def test_small_file_returned_fully(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "test-job"
        log_dir.mkdir(parents=True)
        (log_dir / "small.log").write_text("line1\nline2\n")

        resp = await async_client.get("/api/logs/test-job/small.log")
        assert resp.status_code == 200
        assert "line1" in resp.text
        assert "truncated" not in resp.text

    async def test_large_file_truncated(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "test-job"
        log_dir.mkdir(parents=True)
        with open(log_dir / "large.log", "w") as f:
            for i in range(20000):  # ~2MB
                f.write(f"line-{i:06d}: {'x' * 90}\n")

        resp = await async_client.get("/api/logs/test-job/large.log")
        assert resp.status_code == 200
        assert "truncated" in resp.text
        assert "line-019999" in resp.text  # last line should be present


class TestListLogsPagination:
    async def test_list_logs_respects_limit(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "many-logs"
        log_dir.mkdir(parents=True)
        for i in range(10):
            (log_dir / f"run_{i:02d}.log").write_text(f"log {i}")

        resp = await async_client.get("/api/logs/many-logs?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_list_logs_default_returns_all_under_limit(self, async_client, settings):
        log_dir = Path(settings.logs_dir) / "few-logs"
        log_dir.mkdir(parents=True)
        for i in range(5):
            (log_dir / f"run_{i:02d}.log").write_text(f"log {i}")

        resp = await async_client.get("/api/logs/few-logs")
        assert resp.status_code == 200
        assert len(resp.json()) == 5
