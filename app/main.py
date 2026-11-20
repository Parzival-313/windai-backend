"""FastAPI application factory.

Run with: uvicorn app.main:app  (the compose `api` service does this for you).
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.api.routers import auth, health, turbines
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, request_id_var
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.session import get_sessionmaker
from app.services import auth_service

logger = logging.getLogger("app")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup code goes before `yield`, shutdown code after it.
    settings = get_settings()
    logger.info("api starting", extra={"version": __version__, "env": settings.environment})
    if settings.admin_email and settings.admin_password:
        # First-start bootstrap. Migrations have already run (`alembic upgrade head`).
        with get_sessionmaker()() as db:
            auth_service.bootstrap_admin(db, settings)
    yield
    logger.info("api stopping")


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on bad / missing env
    configure_logging(settings.log_level)

    app = FastAPI(
        title="AEOLUS API",
        version=__version__,
        summary="Screening-level wind resource and energy assessment for Bangladesh.",
        lifespan=lifespan,
    )

    register_error_handlers(app)
    app.state.limiter = limiter  # slowapi looks the limiter up here
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # bearer tokens in headers, no cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        logger.info(
            "request",
            extra={
                "requestId": rid,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    app.include_router(health.router)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(turbines.router, prefix=API_PREFIX)

    return app


app = create_app()
