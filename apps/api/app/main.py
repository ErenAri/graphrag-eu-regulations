import logging
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.api.routes.actions import router as actions_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import (
    observe_http_request,
    observe_rate_limit_backend_error,
    observe_rate_limit_rejection,
)
from app.core.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    resolve_client_identity,
)
from app.core.request_context import reset_request_id, set_request_id
from app.db.migrations import run_migrations
from app.db.neo4j import close_driver

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        ...


rate_limiter: RateLimiter
if settings.rate_limit_backend == "redis" and settings.rate_limit_redis_url:
    rate_limiter = RedisRateLimiter(settings.rate_limit_redis_url)
else:
    rate_limiter = InMemoryRateLimiter()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(actions_router)


def _error_payload(code: str, message: str, request_id: str) -> dict:
    return {
        "error": {"code": code, "message": message},
        "request_id": request_id,
    }


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    started_at = perf_counter()
    route_key = request.url.path
    method = request.method
    status_code = 500
    request_id = request.headers.get("x-request-id") or str(uuid4())
    token = set_request_id(request_id)
    request.state.request_id = request_id
    try:
        if settings.rate_limit_enabled:
            route_limit = settings.rate_limit_route_limits.get(
                route_key,
                settings.rate_limit_requests_per_minute,
            )
            client_host = request.client.host if request.client else None
            client_id = resolve_client_identity(
                request.headers,
                client_host,
                settings.rate_limit_trust_proxy,
            )
            limit_key = f"{request.method}:{route_key}:{client_id}"
            try:
                allowed = rate_limiter.allow(limit_key, route_limit, settings.rate_limit_window_seconds)
            except RedisError:
                logger.exception("rate_limit_backend_error")
                observe_rate_limit_backend_error(settings.rate_limit_backend)
                if not settings.rate_limit_fail_open:
                    status_code = 503
                    response = JSONResponse(
                        status_code=503,
                        content=_error_payload("rate_limit_unavailable", "Rate limiter unavailable", request_id),
                    )
                    response.headers["x-request-id"] = request_id
                    return response
                allowed = True
            if not allowed:
                observe_rate_limit_rejection(method, route_key)
                status_code = 429
                response = JSONResponse(
                    status_code=429,
                    content=_error_payload("rate_limited", "Rate limit exceeded", request_id),
                )
                response.headers["x-request-id"] = request_id
                return response
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        logger.exception("unhandled_server_exception")
        status_code = 500
        response = JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "Internal server error", request_id),
        )
    finally:
        duration = perf_counter() - started_at
        observe_http_request(method, route_key, status_code, duration)
        reset_request_id(token)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload("http_error", str(exc.detail), request_id),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
            "request_id": request_id,
        },
    )


@app.on_event("startup")
def startup() -> None:
    if settings.auto_migrate_on_startup:
        applied = run_migrations(include_seed=False)
        logger.info("startup_migrations_applied:%s", len(applied))
    else:
        logger.info("auto_migrate_disabled")


@app.on_event("shutdown")
def shutdown() -> None:
    close_driver()
