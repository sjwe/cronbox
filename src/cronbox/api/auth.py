import hashlib
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from cronbox.models.auth import APIKey, User, UserRole
from cronbox.models.database import get_session_factory

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class _SyntheticUser:
    """Lightweight stand-in for User that doesn't touch SQLAlchemy instrumentation."""

    def __init__(self, label: str):
        self.id = 0
        self.username = label
        self.email = f"{label}@localhost"
        self.password_hash = ""
        self.role = UserRole.admin
        self.is_active = True
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


def _make_synthetic_admin(label: str = "dev") -> "_SyntheticUser":
    """Create a synthetic admin user for dev/legacy mode."""
    return _SyntheticUser(label)


async def get_current_user(
    request: Request, api_key: str | None = Security(api_key_header)
) -> User:
    settings = request.app.state.settings
    jwt_secret = getattr(settings, "jwt_secret", "")
    legacy_api_key = getattr(settings, "api_key", "")

    # 1. Check X-API-Key header → DB lookup
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            result = await session.execute(
                select(APIKey).where(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active.is_(True),
                )
            )
            db_key = result.scalar_one_or_none()
            if db_key:
                if db_key.expires_at and db_key.expires_at < datetime.utcnow():
                    raise HTTPException(status_code=401, detail="API key expired")
                db_key.last_used_at = datetime.utcnow()
                await session.commit()
                # Eagerly load user
                user_result = await session.execute(
                    select(User).where(User.id == db_key.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user and user.is_active:
                    return user
                raise HTTPException(status_code=401, detail="User inactive")

        # Legacy: check if it matches the configured api_key
        if legacy_api_key and api_key == legacy_api_key:
            return _make_synthetic_admin("legacy-api-key")

        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. Check Authorization: Bearer header → JWT or legacy key
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

        # Try JWT first if jwt_secret is configured
        if jwt_secret:
            try:
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                if payload.get("type") != "access":
                    raise HTTPException(status_code=401, detail="Invalid token type")
                user_id = payload.get("sub")
                session_factory = request.app.state.session_factory
                async with session_factory() as session:
                    result = await session.execute(
                        select(User).where(User.id == int(user_id))
                    )
                    user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user
                raise HTTPException(status_code=401, detail="User not found or inactive")
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token expired")
            except (jwt.InvalidTokenError, ValueError, TypeError):
                pass  # Fall through to legacy check

        # Legacy: check if bearer token matches the configured api_key
        if legacy_api_key and token == legacy_api_key:
            return _make_synthetic_admin("legacy-bearer")

        raise HTTPException(status_code=401, detail="Invalid token")

    # 3. Dev mode: no jwt_secret and no api_key configured → allow all
    if not jwt_secret and not legacy_api_key:
        return _make_synthetic_admin("dev")

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
