class TestApiKeyAuth:
    async def test_no_api_key_configured_allows_all(self, async_client):
        """When CRONBOX_API_KEY is empty, all requests pass through."""
        resp = await async_client.get("/api/jobs")
        assert resp.status_code == 200

    async def test_valid_x_api_key_header(self, async_client, settings):
        """X-API-Key header with correct key passes."""
        settings.api_key = "test-secret-key"
        resp = await async_client.get(
            "/api/jobs", headers={"X-API-Key": "test-secret-key"}
        )
        assert resp.status_code == 200

    async def test_valid_bearer_token(self, async_client, settings):
        """Authorization: Bearer header with correct key passes."""
        settings.api_key = "test-secret-key"
        resp = await async_client.get(
            "/api/jobs", headers={"Authorization": "Bearer test-secret-key"}
        )
        assert resp.status_code == 200

    async def test_missing_key_returns_401(self, async_client, settings):
        """No auth header when key is configured returns 401."""
        settings.api_key = "test-secret-key"
        resp = await async_client.get("/api/jobs")
        assert resp.status_code == 401

    async def test_wrong_key_returns_401(self, async_client, settings):
        """Wrong API key returns 401."""
        settings.api_key = "test-secret-key"
        resp = await async_client.get(
            "/api/jobs", headers={"X-API-Key": "wrong-key"}
        )
        assert resp.status_code == 401

    async def test_auth_applies_to_mutating_endpoints(self, async_client, settings):
        """POST endpoints also require auth."""
        settings.api_key = "test-secret-key"
        resp = await async_client.post("/api/config/reload")
        assert resp.status_code == 401
