"""Application entry point and factory function for Kestrel AI Control Center."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestIdAndLoggingMiddleware
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import clear_refresh_cookie
from app.modules.auth.router import router as auth_router
from app.modules.auth.service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    RegistrationDisabled,
)
from app.modules.auth.sessions import InvalidRefreshToken, RefreshTokenReused
from app.modules.platform.router import router as platform_router
from app.modules.users.router import router as users_router
from app.modules.users.service import LastAdminError, UserNotFound


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    setup_logging(settings)

    is_prod = settings.app_env == "prod"
    app = FastAPI(
        title="Kestrel AI Control Center API",
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # Domain Exception Handlers
    @app.exception_handler(RegistrationDisabled)
    def registration_disabled_handler(request: Request, exc: RegistrationDisabled) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Registration is currently disabled"},
        )

    @app.exception_handler(EmailAlreadyRegistered)
    def email_already_registered_handler(
        request: Request, exc: EmailAlreadyRegistered
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Email already registered"},
        )

    @app.exception_handler(InvalidCredentials)
    def invalid_credentials_handler(request: Request, exc: InvalidCredentials) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(InvalidRefreshToken)
    def invalid_refresh_token_handler(request: Request, exc: InvalidRefreshToken) -> JSONResponse:
        resp = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or expired refresh token"},
        )
        clear_refresh_cookie(resp, settings)
        return resp

    @app.exception_handler(RefreshTokenReused)
    def refresh_token_reused_handler(request: Request, exc: RefreshTokenReused) -> JSONResponse:
        resp = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or expired refresh token"},
        )
        clear_refresh_cookie(resp, settings)
        return resp

    @app.exception_handler(UserNotFound)
    def user_not_found_handler(request: Request, exc: UserNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "User not found"},
        )

    @app.exception_handler(LastAdminError)
    def last_admin_error_handler(request: Request, exc: LastAdminError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Cannot remove the last active admin"},
        )

    app.add_middleware(RequestIdAndLoggingMiddleware)

    # Unversioned infrastructure probes (ADR-014)
    app.include_router(platform_router)

    # Versioned domain APIs (ADR-014)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")

    return app


app = create_app()
