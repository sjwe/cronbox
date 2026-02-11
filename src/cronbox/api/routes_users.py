from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from cronbox.api.permissions import require_admin
from cronbox.models.api_models import CreateUserRequest, UpdateUserRequest, UserResponse
from cronbox.models.auth import User, UserRole, hash_password

router = APIRouter(prefix="/api/admin/users")


@router.get("/", response_model=list[UserResponse], dependencies=[Depends(require_admin)])
async def list_users(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role.value,
        )
        for u in users
    ]


@router.post("/", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def create_user(body: CreateUserRequest, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        # Check duplicates
        existing = await session.execute(
            select(User).where(
                (User.username == body.username) | (User.email == body.email)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username or email already exists")

        user = User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
            role=UserRole(body.role),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
        )


@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def update_user(user_id: int, body: UpdateUserRequest, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if body.role is not None:
            user.role = UserRole(body.role)
        if body.is_active is not None:
            user.is_active = body.is_active

        await session.commit()
        await session.refresh(user)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
        )


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: int, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.is_active = False
        await session.commit()

    return {"message": "User deactivated"}
