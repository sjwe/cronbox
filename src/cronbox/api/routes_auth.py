import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from cronbox.api.auth import get_current_user
from cronbox.models.auth import RefreshToken, User, verify_password
from cronbox.models.api_models import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/api/auth")


def _create_access_token(user: User, secret: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "exp": now + timedelta(minutes=expire_minutes),
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def _create_refresh_token(user: User, session, expire_days: int) -> str:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(days=expire_days)
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(db_token)
    await session.commit()
    return raw


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    settings = request.app.state.settings
    jwt_secret = settings.jwt_secret
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT not configured")

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == body.username)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account disabled")

        expire_minutes = settings.access_token_expire_minutes
        access_token = _create_access_token(user, jwt_secret, expire_minutes)

        refresh_days = settings.refresh_token_expire_days
        refresh_token = await _create_refresh_token(user, session, refresh_days)

    response.set_cookie(
        key="cronbox_refresh",
        value=refresh_token,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
        refresh_token=refresh_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
        ),
    )


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    settings = request.app.state.settings
    jwt_secret = settings.jwt_secret
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT not configured")

    # Read token from body first, then cookie
    token = None
    try:
        body = await request.json()
        token = body.get("refresh_token")
    except Exception:
        pass
    if not token:
        token = request.cookies.get("cronbox_refresh")

    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        db_token = result.scalar_one_or_none()

        if not db_token or db_token.revoked:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        if db_token.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Refresh token expired")

        # Get user
        user_result = await session.execute(
            select(User).where(User.id == db_token.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        # Revoke old token
        db_token.revoked = True
        await session.commit()

        # Create new tokens
        expire_minutes = settings.access_token_expire_minutes
        access_token = _create_access_token(user, jwt_secret, expire_minutes)
        refresh_days = settings.refresh_token_expire_days
        new_refresh = await _create_refresh_token(user, session, refresh_days)

    response.set_cookie(
        key="cronbox_refresh",
        value=new_refresh,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expire_minutes * 60,
        "refresh_token": new_refresh,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("cronbox_refresh")
    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token")
        except Exception:
            pass

    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            result = await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            db_token = result.scalar_one_or_none()
            if db_token:
                db_token.revoked = True
                await session.commit()

    response.delete_cookie("cronbox_refresh")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
    )
