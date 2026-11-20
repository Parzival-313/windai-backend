"""API tests for /api/v1/auth against the local test database."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core import security
from app.models.user import RefreshToken, User
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

AUTH = "/api/v1/auth"
NEW_PASSWORD = "another-long-password-2"


def _err(r) -> dict:
    body = r.json()
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- login -------------------------------------------------------------------------


def test_login_returns_token_pair(client, admin_user, db):
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"accessToken", "refreshToken", "tokenType", "expiresIn"}
    assert body["tokenType"] == "bearer"
    assert body["expiresIn"] == 30 * 60
    db.refresh(admin_user)
    assert admin_user.last_login_at is not None


def test_login_email_is_case_insensitive(client, admin_user):
    assert login(client, email="  ADMIN@Example.COM ").status_code == 200


def test_login_wrong_password_and_unknown_email_look_the_same(client, admin_user):
    wrong_pw = login(client, password="not-the-password")
    unknown = login(client, email="nobody@example.com")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert _err(wrong_pw) == _err(unknown)
    assert _err(wrong_pw)["code"] == "INVALID_CREDENTIALS"
    assert wrong_pw.headers["WWW-Authenticate"] == "Bearer"


def test_login_inactive_user_rejected(client, admin_user, db):
    db.execute(update(User).values(is_active=False))
    db.commit()
    assert login(client).status_code == 401


def test_login_rate_limited_on_sixth_attempt(client, admin_user):
    codes = [login(client, password="wrong-password").status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    r = login(client)  # even the right password is blocked now
    assert r.status_code == 429
    assert _err(r)["code"] == "RATE_LIMITED"
    assert r.headers["Retry-After"] == "60"


def test_login_validation_error(client, db):
    r = client.post(f"{AUTH}/login", json={"email": "a@b.c"})
    assert r.status_code == 422
    assert _err(r)["code"] == "VALIDATION_ERROR"


# --- /me and the bearer dependency -------------------------------------------------


def test_me(client, auth_headers, admin_user):
    r = client.get(f"{AUTH}/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "email", "createdAt", "lastLoginAt"}
    assert body["id"] == str(admin_user.id)
    assert body["email"] == ADMIN_EMAIL
    assert body["lastLoginAt"] is not None


def test_me_without_token(client, db):
    r = client.get(f"{AUTH}/me")
    assert r.status_code == 401
    assert _err(r)["code"] == "NOT_AUTHENTICATED"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_me_with_garbage_token(client, db):
    r = client.get(f"{AUTH}/me", headers=_bearer("not.a.jwt"))
    assert r.status_code == 401
    assert _err(r)["code"] == "INVALID_TOKEN"


def test_me_with_expired_token(client, admin_user):
    token = security.create_access_token(admin_user.id, now=datetime.now(UTC) - timedelta(hours=1))
    r = client.get(f"{AUTH}/me", headers=_bearer(token))
    assert r.status_code == 401
    assert _err(r)["code"] == "TOKEN_EXPIRED"


def test_me_token_for_deleted_user(client, db):
    token = security.create_access_token(uuid.uuid4())
    r = client.get(f"{AUTH}/me", headers=_bearer(token))
    assert r.status_code == 401
    assert _err(r)["code"] == "INVALID_TOKEN"


# --- refresh rotation --------------------------------------------------------------


def _refresh(client, token: str):
    return client.post(f"{AUTH}/refresh", json={"refreshToken": token})


def test_refresh_rotates_and_old_token_is_rejected(client, tokens):
    r = _refresh(client, tokens["refreshToken"])
    assert r.status_code == 200
    new = r.json()
    assert new["refreshToken"] != tokens["refreshToken"]
    assert client.get(f"{AUTH}/me", headers=_bearer(new["accessToken"])).status_code == 200

    reused = _refresh(client, tokens["refreshToken"])
    assert reused.status_code == 401
    assert _err(reused)["code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_reuse_revokes_whole_family(client, tokens):
    new = _refresh(client, tokens["refreshToken"]).json()
    assert _refresh(client, tokens["refreshToken"]).status_code == 401  # replay -> theft
    # The legitimate newest token is now dead as well.
    assert _refresh(client, new["refreshToken"]).status_code == 401


def test_refresh_chain_works_repeatedly(client, tokens):
    token = tokens["refreshToken"]
    for _ in range(3):
        r = _refresh(client, token)
        assert r.status_code == 200
        token = r.json()["refreshToken"]


def test_refresh_unknown_token(client, db):
    assert _refresh(client, "x" * 64).status_code == 401


def test_refresh_expired_token(client, tokens, db):
    db.execute(update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    assert _refresh(client, tokens["refreshToken"]).status_code == 401


def test_refresh_tokens_stored_hashed(client, tokens, db):
    hashes = db.scalars(select(RefreshToken.token_hash)).all()
    assert tokens["refreshToken"] not in hashes
    assert security.hash_refresh_token(tokens["refreshToken"]) in hashes


# --- logout ------------------------------------------------------------------------


def test_logout_revokes_refresh_token(client, tokens, auth_headers):
    r = client.post(
        f"{AUTH}/logout", json={"refreshToken": tokens["refreshToken"]}, headers=auth_headers
    )
    assert r.status_code == 204
    assert _refresh(client, tokens["refreshToken"]).status_code == 401
    # Idempotent
    again = client.post(
        f"{AUTH}/logout", json={"refreshToken": tokens["refreshToken"]}, headers=auth_headers
    )
    assert again.status_code == 204


def test_logout_requires_auth(client, tokens):
    r = client.post(f"{AUTH}/logout", json={"refreshToken": tokens["refreshToken"]})
    assert r.status_code == 401
    assert _refresh(client, tokens["refreshToken"]).status_code == 200  # not revoked


# --- change password ---------------------------------------------------------------


def _change(client, headers, current: str, new: str):
    return client.post(
        f"{AUTH}/change-password",
        json={"currentPassword": current, "newPassword": new},
        headers=headers,
    )


def test_change_password_revokes_all_refresh_tokens(client, tokens, auth_headers):
    second = login(client).json()  # another "device"
    r = _change(client, auth_headers, ADMIN_PASSWORD, NEW_PASSWORD)
    assert r.status_code == 204

    assert _refresh(client, tokens["refreshToken"]).status_code == 401
    assert _refresh(client, second["refreshToken"]).status_code == 401
    assert login(client).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_change_password_wrong_current(client, auth_headers):
    r = _change(client, auth_headers, "wrong-current-pw", NEW_PASSWORD)
    assert r.status_code == 400
    assert _err(r)["code"] == "INVALID_CURRENT_PASSWORD"


def test_change_password_same_as_current(client, auth_headers):
    r = _change(client, auth_headers, ADMIN_PASSWORD, ADMIN_PASSWORD)
    assert r.status_code == 400
    assert _err(r)["code"] == "PASSWORD_UNCHANGED"


def test_change_password_too_short(client, auth_headers):
    r = _change(client, auth_headers, ADMIN_PASSWORD, "short")
    assert r.status_code == 422
    assert _err(r)["details"]["fields"][0]["field"] == "newPassword"


def test_change_password_requires_auth(client, db):
    r = _change(client, {}, ADMIN_PASSWORD, NEW_PASSWORD)
    assert r.status_code == 401


def test_no_registration_endpoint(client, db):
    r = client.post(f"{AUTH}/register", json={"email": "x@y.z", "password": "p" * 12})
    assert r.status_code == 404
