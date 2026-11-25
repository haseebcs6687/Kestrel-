"""Request-ID extraction and access-log middleware for HTTP requests."""

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
logger = structlog.get_logger("kestrel.access")


class RequestIdAndLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns/validates X-Request-ID and logs request access details."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        structlog.contextvars.clear_contextvars()
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        if incoming_id and REQUEST_ID_PATTERN.match(incoming_id):
            request_id = incoming_id
        else:
            request_id = uuid.uuid4().hex

        structlog.contextvars.bind_contextvars(request_id=request_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
