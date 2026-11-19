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

from app import __version__
from app.api.routers import health
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, request_id_var

logger = logging.getLogger("app")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup code goes before `yield`, shutdown code after it.
    settings = get_settings()
    logger.info("api starting", extra={"version": __version__, "env": settings.environment})
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
    # Domain routers are mounted under API_PREFIX from Step 1 onwards.

    return app


app = create_app()
