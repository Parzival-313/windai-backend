"""Shared FastAPI dependencies (`Depends(...)`).

A dependency is a function FastAPI calls before your handler and injects the result —
like a Gin middleware that does `c.Set("user", u)`, but typed and per-route.
Every protected route in later steps declares `user: CurrentUser`.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

# auto_error=False: we raise our own error shape instead of FastAPI's default 403.
# This also adds the "Authorize" button (paste the access token) to Swagger /docs.
_bearer = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.", code="NOT_AUTHENTICATED")
    return auth_service.user_from_access_token(db, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]

__all__ = ["CurrentUser", "DbSession", "get_current_user", "get_db"]
