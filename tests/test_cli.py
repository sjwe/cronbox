import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import cronbox.models.auth  # noqa: F401
import cronbox.models.database as db_module
from cronbox.models.auth import User
from cronbox.models.database import Base


class TestCreateUser:
    async def test_create_user_success(self, db_engine, db_session_factory, monkeypatch):
        """CLI create-user creates a user in the database."""
        # Patch DB globals so cli uses in-memory DB
        monkeypatch.setattr(db_module, "_engine", db_engine)
        monkeypatch.setattr(db_module, "_session_factory", db_session_factory)

        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        from cronbox.cli import _create_user

        class Args:
            username = "testuser"
            email = "test@test.com"
            role = "admin"
            password = "test-password"

        await _create_user(Args())

        async with db_session_factory() as session:
            result = await session.execute(
                select(User).where(User.username == "testuser")
            )
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.email == "test@test.com"
            assert user.role.value == "admin"

    async def test_create_user_duplicate(self, db_engine, db_session_factory, monkeypatch):
        """CLI create-user rejects duplicate username/email."""
        monkeypatch.setattr(db_module, "_engine", db_engine)
        monkeypatch.setattr(db_module, "_session_factory", db_session_factory)

        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        from cronbox.cli import _create_user

        class Args:
            username = "dupuser"
            email = "dup@test.com"
            role = "viewer"
            password = "test-password"

        await _create_user(Args())

        with pytest.raises(SystemExit):
            await _create_user(Args())
