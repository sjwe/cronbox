import hashlib
from datetime import datetime, timedelta, timezone

from cronbox.models.auth import APIKey, generate_api_key


class TestCreateKey:
    async def test_create_key_returns_full_key(self, auth_async_client, admin_user, admin_token):
        resp = await auth_async_client.post(
            "/api/keys",
            json={"name": "my-key"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "key" in data
        assert data["key"].startswith("cb_")
        assert data["key_prefix"] == data["key"][:12]
        assert data["name"] == "my-key"


class TestListKeys:
    async def test_list_keys_hides_full_key(self, auth_async_client, admin_user, admin_token):
        # Create a key
        await auth_async_client.post(
            "/api/keys",
            json={"name": "list-test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # List keys
        resp = await auth_async_client.get(
            "/api/keys",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert "key" not in item  # full key not exposed
            assert "key_prefix" in item


class TestRevokeKey:
    async def test_revoke_key(self, auth_async_client, admin_user, admin_token):
        # Create a key
        create_resp = await auth_async_client.post(
            "/api/keys",
            json={"name": "revoke-test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key_id = create_resp.json()["id"]

        # Revoke
        resp = await auth_async_client.delete(
            f"/api/keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

        # Verify it shows as inactive
        list_resp = await auth_async_client.get(
            "/api/keys",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        revoked = [k for k in list_resp.json() if k["id"] == key_id]
        assert revoked[0]["is_active"] is False


class TestAuthWithAPIKey:
    async def test_auth_with_api_key(self, auth_async_client, admin_user, admin_token):
        # Create a key via JWT auth
        create_resp = await auth_async_client.post(
            "/api/keys",
            json={"name": "auth-test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        full_key = create_resp.json()["key"]

        # Use the API key to access a protected endpoint
        resp = await auth_async_client.get(
            "/api/jobs",
            headers={"X-API-Key": full_key},
        )
        assert resp.status_code == 200

    async def test_expired_key_rejected(
        self, auth_async_client, admin_user, admin_token, db_session_factory
    ):
        # Create a key
        create_resp = await auth_async_client.post(
            "/api/keys",
            json={"name": "expire-test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key_id = create_resp.json()["id"]
        full_key = create_resp.json()["key"]

        # Manually set expiry to the past
        async with db_session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(APIKey).where(APIKey.id == key_id)
            )
            db_key = result.scalar_one()
            db_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            await session.commit()

        resp = await auth_async_client.get(
            "/api/jobs",
            headers={"X-API-Key": full_key},
        )
        assert resp.status_code == 401

    async def test_revoked_key_rejected(self, auth_async_client, admin_user, admin_token):
        # Create and revoke a key
        create_resp = await auth_async_client.post(
            "/api/keys",
            json={"name": "revoke-auth-test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        key_id = create_resp.json()["id"]
        full_key = create_resp.json()["key"]

        await auth_async_client.delete(
            f"/api/keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        resp = await auth_async_client.get(
            "/api/jobs",
            headers={"X-API-Key": full_key},
        )
        assert resp.status_code == 401
