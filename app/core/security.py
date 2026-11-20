"""Password hashing, access JWTs and refresh-token helpers. Pure functions, no DB.

- Passwords: Argon2id via pwdlib (memory-hard; the modern default, like Go's
  `golang.org/x/crypto/argon2`). Only the hash is ever stored.
- Access token: a short-lived signed JWT (HS256 with JWT_SECRET). The API trusts it
  without a DB lookup of the token itself, so it cannot be revoked — keep it short.
- Refresh token: an opaque random string (not a JWT). The DB stores only its
  SHA-256, so a leaked DB dump cannot be replayed. SHA-256 (not Argon2) is right
  here because the token already has 384 bits of randomness — nothing to brute-force.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "aeolus"
ACCESS_TOKEN_TYPE = "access"

PASSWORD_MIN_LENGTH = 6  # team decision 2026-11-20 (design said 12); login is rate-limited
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHash.recommended()  # Argon2id with library-recommended parameters
# Used when the email is unknown, so a failed login costs the same time either way
# (otherwise response timing would reveal whether an email exists).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


# --- passwords ---------------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-work check. Pass `None` for an unknown user: still runs one Argon2 verify."""
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def password_problem(password: str) -> str | None:
    """Return a human-readable reason the password is unacceptable, or None if it is fine."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
    if not password.strip():
        return "Password must not be only whitespace."
    return None


# --- access JWT --------------------------------------------------------------------


class TokenError(Exception):
    """Access token is missing claims, has a bad signature, or is otherwise invalid."""


class TokenExpiredError(TokenError):
    pass


def create_access_token(user_id: uuid.UUID, *, now: datetime | None = None) -> str:
    settings = get_settings()
    now = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    """Verify signature, issuer, expiry and type; return the user id (`sub`)."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],  # never accept "none" or an attacker-chosen algorithm
            issuer=JWT_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Access token is invalid.") from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise TokenError("Not an access token.")
    try:
        return uuid.UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise TokenError("Access token subject is invalid.") from exc


# --- refresh tokens ----------------------------------------------------------------


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)  # 48 random bytes -> 64 URL-safe characters


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
