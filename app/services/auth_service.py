"""Auth business logic: admin creation, login, refresh rotation, logout, password change.

Functions take a SQLAlchemy `Session` and commit their own unit of work, like a Go
service method that receives `*sql.DB` and runs one transaction.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ConflictError, UnauthorizedError
from app.models.user import RefreshToken, User

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _now() -> datetime:
    return datetime.now(UTC)


def _invalid_credentials() -> UnauthorizedError:
    # One generic message for unknown email, wrong password and inactive user.
    return UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")


def _invalid_refresh() -> UnauthorizedError:
    return UnauthorizedError(
        "Refresh token is invalid, expired or revoked.", code="INVALID_REFRESH_TOKEN"
    )


# --- admin creation ----------------------------------------------------------------


def user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def validate_new_credentials(email: str, password: str) -> None:
    if not _EMAIL_RE.match(email):
        raise AppError("Email address is not valid.", code="INVALID_EMAIL")
    if problem := security.password_problem(password):
        raise AppError(problem, code="WEAK_PASSWORD")


def create_admin(db: Session, email: str, password: str) -> User:
    """Create the single admin user. Refuses if any user already exists."""
    email = normalize_email(email)
    validate_new_credentials(email, password)
    if user_count(db) > 0:
        raise ConflictError("An admin user already exists.", code="ADMIN_EXISTS")
    user = User(email=email, password_hash=security.hash_password(password))
    db.add(user)
    db.commit()
    return user


def reset_password(db: Session, new_password: str) -> User:
    """CLI `create-admin --reset-password`: set the existing admin's password."""
    if problem := security.password_problem(new_password):
        raise AppError(problem, code="WEAK_PASSWORD")
    user = db.scalars(select(User).order_by(User.created_at)).first()
    if user is None:
        raise AppError("No admin user exists yet; run create-admin first.", code="NO_ADMIN")
    user.password_hash = security.hash_password(new_password)
    _revoke_all(db, user.id)
    db.commit()
    return user


def bootstrap_admin(db: Session, settings: Settings) -> bool:
    """First start in Docker: create the admin from ADMIN_EMAIL/ADMIN_PASSWORD if no user exists.

    Returns True if a user was created. Never logs the password.
    """
    if not (settings.admin_email and settings.admin_password):
        return False
    if user_count(db) > 0:
        logger.warning(
            "ADMIN_PASSWORD is set but ignored because an admin already exists; remove it from .env"
        )
        return False
    user = create_admin(db, settings.admin_email, settings.admin_password.get_secret_value())
    logger.info("admin created from environment", extra={"email": user.email})
    return True


# --- tokens ------------------------------------------------------------------------


def _issue_pair(
    db: Session, user: User, family_id: uuid.UUID | None = None
) -> tuple[TokenPair, RefreshToken]:
    settings = get_settings()
    raw = security.new_refresh_token()
    row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=security.hash_refresh_token(raw),
        expires_at=_now() + timedelta(days=settings.refresh_token_days),
    )
    db.add(row)
    pair = TokenPair(
        access_token=security.create_access_token(user.id),
        refresh_token=raw,
        expires_in=settings.access_token_minutes * 60,
    )
    return pair, row


def _revoke_all(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def login(db: Session, email: str, password: str) -> TokenPair:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    # verify_password(None) still burns one Argon2 verify, so timing does not leak
    # whether the email exists.
    ok = security.verify_password(password, user.password_hash if user else None)
    if not ok or user is None or not user.is_active:
        raise _invalid_credentials()

    user.last_login_at = _now()
    pair, _ = _issue_pair(db, user)
    db.commit()
    return pair


def refresh(db: Session, raw_token: str) -> TokenPair:
    """Rotate: the presented token is revoked and a new pair is issued (same family)."""
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == security.hash_refresh_token(raw_token))
        .with_for_update()  # two concurrent refreshes with one token: only one wins
    )
    if row is None:
        raise _invalid_refresh()

    if row.revoked_at is not None:
        if row.replaced_by_id is not None:
            # A token that was already rotated is being replayed: assume theft and
            # kill the whole chain, including the legitimate newest token.
            db.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=_now())
            )
            db.commit()
            logger.warning(
                "refresh token reuse detected; token family revoked",
                extra={"userId": str(row.user_id)},
            )
        raise _invalid_refresh()

    if row.expires_at <= _now():
        raise _invalid_refresh()

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise _invalid_refresh()

    pair, new_row = _issue_pair(db, user, family_id=row.family_id)
    db.flush()  # write new_row first so the replaced_by_id foreign key is satisfied
    row.revoked_at = _now()
    row.replaced_by_id = new_row.id
    db.commit()
    return pair


def logout(db: Session, user: User, raw_token: str) -> None:
    """Revoke one refresh token of this user. Idempotent: unknown/revoked tokens are ignored."""
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == security.hash_refresh_token(raw_token),
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    db.commit()


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not security.verify_password(current_password, user.password_hash):
        # 400, not 401: the session is fine, only the form value is wrong. A 401 would
        # make a client think it was logged out.
        raise AppError("Current password is incorrect.", code="INVALID_CURRENT_PASSWORD")
    if security.verify_password(new_password, user.password_hash):
        raise AppError("New password must differ from the current one.", code="PASSWORD_UNCHANGED")
    if problem := security.password_problem(new_password):
        raise AppError(problem, code="WEAK_PASSWORD")

    user.password_hash = security.hash_password(new_password)
    _revoke_all(db, user.id)  # every device must log in again
    db.commit()


def user_from_access_token(db: Session, token: str) -> User:
    try:
        user_id = security.decode_access_token(token)
    except security.TokenExpiredError as exc:
        raise UnauthorizedError("Access token has expired.", code="TOKEN_EXPIRED") from exc
    except security.TokenError as exc:
        raise UnauthorizedError("Access token is invalid.", code="INVALID_TOKEN") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Access token is invalid.", code="INVALID_TOKEN")
    return user
