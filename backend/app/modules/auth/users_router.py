"""User management endpoints scoped strictly to the authenticated workspace."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary="List users in the caller's workspace (Admin only)",
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
