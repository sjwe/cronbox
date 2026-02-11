from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from cronbox.api.auth import get_current_user
from cronbox.models.api_models import APIKeyListItem, APIKeyResponse, CreateAPIKeyRequest
from cronbox.models.auth import APIKey, User, UserRole, generate_api_key

router = APIRouter(prefix="/api/keys")


@router.post("/", response_model=APIKeyResponse)
async def create_key(
    body: CreateAPIKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    settings = request.app.state.settings
    expire_days = body.expires_in_days or settings.api_key_default_expire_days

    full_key, key_prefix, key_hash = generate_api_key()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expire_days)

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        db_key = APIKey(
            user_id=current_user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=body.name,
            expires_at=expires_at,
        )
        session.add(db_key)
        await session.commit()
        await session.refresh(db_key)

        return APIKeyResponse(
            id=db_key.id,
            key=full_key,
            key_prefix=key_prefix,
            name=db_key.name,
            expires_at=db_key.expires_at,
            created_at=db_key.created_at,
        )


@router.get("/", response_model=list[APIKeyListItem])
async def list_keys(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(APIKey).where(APIKey.user_id == current_user.id)
        )
        keys = result.scalars().all()

    return [
        APIKeyListItem(
            id=k.id,
            key_prefix=k.key_prefix,
            name=k.name,
            expires_at=k.expires_at,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            is_active=k.is_active,
        )
        for k in keys
    ]


@router.delete("/{key_id}")
async def revoke_key(
    key_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        db_key = result.scalar_one_or_none()

        if not db_key:
            raise HTTPException(status_code=404, detail="API key not found")

        # Only owner or admin can revoke
        if db_key.user_id != current_user.id and current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="Not authorized")

        db_key.is_active = False
        await session.commit()

    return {"message": "API key revoked"}
