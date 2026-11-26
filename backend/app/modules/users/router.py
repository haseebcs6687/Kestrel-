"""Workspace user management endpoints (Admin only)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import UserRead
from app.modules.users.schemas import CreateUserRequest, UpdateUserRequest
from app.modules.users.service import create_user, get_user, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user in caller's workspace (Admin only)",
)
def create_workspace_user(
    payload: CreateUserRequest,
    admin_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Create a new user scoped to the caller's workspace."""
    user = create_user(
        db=db,
        actor_user=admin_user,
        email=payload.email,
        password=payload.password,
        role=payload.role,
    )
    return UserRead.model_validate(user)


@router.get(
    "",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary="List users in caller's workspace (Admin only)",
)
def list_workspace_users(
    admin_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserRead]:
    """Retrieve users belonging to the caller's workspace with pagination support."""
    repo = UserRepository(session=db, workspace_id=admin_user.workspace_id)
    users = repo.list_users(limit=limit, offset=offset)
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get a user by ID within caller's workspace (Admin only)",
)
def get_workspace_user(
    user_id: uuid.UUID,
    admin_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Retrieve a single user in caller's workspace by UUID."""
    user = get_user(db=db, workspace_id=admin_user.workspace_id, user_id=user_id)
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Update user role or active status (Admin only)",
)
def update_workspace_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    admin_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Update role or activation status under a workspace lock with last-admin protection."""
    user = update_user(
        db=db,
        actor_user=admin_user,
        target_user_id=user_id,
        role=payload.role,
        is_active=payload.is_active,
    )
    return UserRead.model_validate(user)
