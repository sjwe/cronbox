import pytest


class TestLogin:
    async def test_login_valid_credentials(self, auth_async_client, admin_user):
        resp = await auth_async_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        assert "refresh_token" in data
        assert "cronbox_refresh" in resp.cookies

    async def test_login_invalid_password(self, auth_async_client, admin_user):
        resp = await auth_async_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-pass"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, auth_async_client):
        resp = await auth_async_client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "pass"},
        )
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_valid(self, auth_async_client, admin_user):
        # First login
        login_resp = await auth_async_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        resp = await auth_async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_revoked(self, auth_async_client, admin_user):
        # Login
        login_resp = await auth_async_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Use the refresh token (this revokes it and issues a new one)
        await auth_async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # Try using the old token again — should fail
        resp = await auth_async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_revokes_token(self, auth_async_client, admin_user):
        # Login
        login_resp = await auth_async_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Logout
        resp = await auth_async_client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200

        # Try to refresh with the revoked token
        resp = await auth_async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_returns_user(self, auth_async_client, admin_user, admin_token):
        resp = await auth_async_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"
