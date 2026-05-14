import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.logging_config import get_logger

logger = get_logger("http")

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        level = logger.warning if response.status_code >= 400 else logger.info
        level(
            f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.0f}ms)"
        )

        return response
