"""Pure unit tests for app/core/security.py (no DB)."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.config import get_settings


def test_password_hash_is_argon2id_and_verifies():
    h = security.hash_password("a-long-enough-password")
    assert h.startswith("$argon2id$")
    assert security.verify_password("a-long-enough-password", h)
    assert not security.verify_password("wrong-password-xx", h)


def test_verify_unknown_user_is_false():
    assert security.verify_password("anything", None) is False


@pytest.mark.parametrize(
    ("password", "ok"),
    [("short", False), ("x" * 6, True), ("x" * 12, True), ("x" * 129, False), (" " * 20, False)],
)
def test_password_policy(password, ok):
    assert (security.password_problem(password) is None) is ok


def test_access_token_roundtrip():
    uid = uuid.uuid4()
    assert security.decode_access_token(security.create_access_token(uid)) == uid


def test_access_token_expired():
    past = datetime.now(UTC) - timedelta(hours=2)
    token = security.create_access_token(uuid.uuid4(), now=past)
    with pytest.raises(security.TokenExpiredError):
        security.decode_access_token(token)


def test_access_token_wrong_secret_rejected():
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "iss": "aeolus", "iat": 0, "exp": 2**40},
        "another-secret-that-is-long-enough-123456",
        algorithm="HS256",
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_access_token_alg_none_rejected():
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "iss": "aeolus", "iat": 0, "exp": 2**40},
        None,
        algorithm="none",
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_non_access_token_type_rejected():
    secret = get_settings().jwt_secret.get_secret_value()
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh", "iss": "aeolus", "iat": 0, "exp": 2**40},
        secret,
        algorithm="HS256",
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_refresh_token_random_and_hash_stable():
    a, b = security.new_refresh_token(), security.new_refresh_token()
    assert a != b and len(a) >= 64
    assert security.hash_refresh_token(a) == security.hash_refresh_token(a)
    assert len(security.hash_refresh_token(a)) == 64
