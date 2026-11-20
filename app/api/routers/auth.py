"""`/api/v1/auth` — login, token refresh/rotation, logout, current user, password change.

There is deliberately no registration endpoint: the single admin is created with the
CLI (`python -m app.cli create-admin`) or the first-start env bootstrap.
"""

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import limiter, login_limit
from app.schemas.auth import (
    ChangePasswordIn,
    LoginIn,
    LogoutIn,
    RefreshIn,
    TokenPairOut,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_401 = {401: {"description": "Not authenticated / invalid token"}}


def _pair_out(pair: auth_service.TokenPair) -> TokenPairOut:
    return TokenPairOut(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post(
    "/login",
    response_model=TokenPairOut,
    summary="Log in (no auth; rate-limited per IP)",
    responses={
        401: {"description": "Invalid email or password"},
        429: {"description": "Too many attempts"},
    },
)
@limiter.limit(login_limit)
def login(request: Request, body: LoginIn, db: DbSession) -> TokenPairOut:
    # `request` is unused here but slowapi needs it to read the client IP.
    return _pair_out(auth_service.login(db, body.email, body.password))


@router.post(
    "/refresh",
    response_model=TokenPairOut,
    summary="Exchange a refresh token for a new pair (no auth; old token is revoked)",
    responses={401: {"description": "Refresh token invalid, expired, revoked or reused"}},
)
def refresh(body: RefreshIn, db: DbSession) -> TokenPairOut:
    return _pair_out(auth_service.refresh(db, body.refresh_token))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
    responses=_401,
)
def logout(body: LogoutIn, user: CurrentUser, db: DbSession) -> None:
    auth_service.logout(db, user, body.refresh_token)


@router.get("/me", response_model=UserOut, summary="Current user", responses=_401)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password; revokes every refresh token",
    responses={**_401, 400: {"description": "Current password wrong / unchanged"}},
)
@limiter.limit(login_limit)
def change_password(
    request: Request, body: ChangePasswordIn, user: CurrentUser, db: DbSession
) -> None:
    auth_service.change_password(db, user, body.current_password, body.new_password)
