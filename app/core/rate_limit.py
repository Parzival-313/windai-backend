"""Per-IP rate limiting (slowapi, a port of Flask-Limiter).

Used as a decorator on an endpoint: `@limiter.limit(login_limit)`. The endpoint
must take `request: Request` so slowapi can read the client IP.

Storage is in-process memory: fine for one API process and a single user. The
counters reset when the API restarts. (Use `storage_uri=redis://...` if the API is
ever run with several worker processes.)
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_body

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


def login_limit() -> str:
    """Read the limit at request time, so LOGIN_RATE_LIMIT changes need no code change."""
    return get_settings().login_rate_limit


async def rate_limit_exceeded_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        error_body(
            "RATE_LIMITED",
            "Too many attempts. Try again later.",
            {"limit": str(exc.detail)},
        ),
        status_code=429,
        # Upper bound for a per-minute window; clients should wait at most this long.
        headers={"Retry-After": "60"},
    )
