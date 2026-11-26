"""Authentication endpoints: registration, login token issuance, and user profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserRead,
    WorkspaceRead,
)
from app.modules.auth.security import create_access_token
from app.modules.auth.service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    RegistrationDisabled,
    authenticate,
    register,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account and organization workspace",
)
def register_user(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRead:
    """Register an administrative user and instantiate a dedicated workspace."""
    try:
        user = register(
            db=db,
            email=payload.email,
            password=payload.password,
            workspace_name=payload.workspace_name,
            settings=settings,
        )
    except RegistrationDisabled as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled",
        ) from exc
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue bearer access token",
)
def login_user(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Verify credentials and issue a short-lived bearer access token."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    try:
        user = authenticate(db=db, email=payload.email, password=payload.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token, expires_in = create_access_token(user_id=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106
        expires_in=expires_in,
    )


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current user profile and workspace information",
)
def get_current_user_profile(
    current_user: CurrentUser,
) -> MeResponse:
    """Return the authenticated user's profile and associated workspace metadata."""
    workspace = current_user.workspace
    workspace_read = WorkspaceRead.model_validate(workspace)

    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        workspace_id=current_user.workspace_id,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        workspace=workspace_read,
    )
