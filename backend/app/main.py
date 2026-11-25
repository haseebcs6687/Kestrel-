"""Application entry point and factory function for Kestrel AI Control Center."""

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestIdAndLoggingMiddleware
from app.modules.platform.router import router as platform_router


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

    app.add_middleware(RequestIdAndLoggingMiddleware)
    app.include_router(platform_router)

    return app


app = create_app()
