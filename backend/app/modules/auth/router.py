"""Authentication endpoints: registration, login, refresh rotation, and user profile."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    Settings,
    get_settings,
)
from app.core.db import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import (
    ChangePasswordRequest,
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
    change_password,
    register,
)
from app.modules.auth.sessions import (
    issue_refresh_token,
    revoke_family_by_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def set_refresh_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    """Attach the HttpOnly refresh token cookie to the response."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.is_cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    """Instruct the user agent to delete the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_cookie_secure,
        samesite="strict",
    )


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
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Verify credentials, issue access token, and attach refresh token cookie."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    try:
        user = authenticate(
            db=db,
            email=payload.email,
            password=payload.password,
        )
        raw_refresh_token, _ = issue_refresh_token(
            db=db,
            user=user,
            workspace_id=user.workspace_id,
        )
        db.commit()
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    set_refresh_cookie(response, raw_refresh_token, settings)
    token, expires_in = create_access_token(user_id=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106
        expires_in=expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new bearer access token",
)
def refresh_session(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_kestrel_client: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    """Rotate the presented refresh token and set a new cookie."""
    if x_kestrel_client != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF client header",
        )

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token cookie",
        )

    access_token, new_raw, _ = rotate_refresh_token(
        db,
        raw_token=refresh_token,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    set_refresh_cookie(response, new_raw, settings)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # noqa: S106
        expires_in=settings.access_token_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke refresh token family and clear session cookie",
)
def logout_user(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_kestrel_client: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> Response:
    """Idempotently invalidate refresh token family and delete refresh cookie."""
    if x_kestrel_client != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF client header",
        )

    if refresh_token:
        revoke_family_by_token(
            db,
            raw_token=refresh_token,
        )

    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(resp, settings)
    return resp


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


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change user password and revoke all active refresh tokens",
)
def change_user_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Change the authenticated user's password, invalidate all sessions, and clear cookie."""
    change_password(
        db=db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    response.headers["Cache-Control"] = "no-store"
    clear_refresh_cookie(response, settings)
    return response
