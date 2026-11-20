"""Admin creation: service rules, CLI `create-admin`, and the first-start env bootstrap."""

import logging

import pytest
from sqlalchemy import select

from app import cli
from app.core import security
from app.core.config import Settings
from app.core.errors import AppError, ConflictError
from app.models.user import RefreshToken, User
from app.services import auth_service
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

SECRET = "s" * 40


def _prompts(*answers: str):
    it = iter(answers)
    return lambda _prompt: next(it)


# --- service -----------------------------------------------------------------------


def test_create_admin_hashes_and_normalizes(db):
    user = auth_service.create_admin(db, "  Admin@Example.com ", ADMIN_PASSWORD)
    assert user.email == "admin@example.com"
    assert user.password_hash != ADMIN_PASSWORD
    assert security.verify_password(ADMIN_PASSWORD, user.password_hash)


def test_only_one_admin_allowed(db, admin_user):
    with pytest.raises(ConflictError):
        auth_service.create_admin(db, "second@example.com", ADMIN_PASSWORD)


@pytest.mark.parametrize(
    ("email", "password", "code"),
    [("not-an-email", ADMIN_PASSWORD, "INVALID_EMAIL"), (ADMIN_EMAIL, "short", "WEAK_PASSWORD")],
)
def test_create_admin_validation(db, email, password, code):
    with pytest.raises(AppError) as info:
        auth_service.create_admin(db, email, password)
    assert info.value.code == code


# --- CLI ---------------------------------------------------------------------------


def test_cli_creates_admin(db):
    out: list[str] = []
    code = cli.create_admin(
        reset_password=False,
        input_fn=_prompts(ADMIN_EMAIL),
        getpass_fn=_prompts(ADMIN_PASSWORD, ADMIN_PASSWORD),
        out=out.append,
    )
    assert code == 0
    assert db.scalar(select(User.email)) == ADMIN_EMAIL
    assert ADMIN_PASSWORD not in " ".join(out)


def test_cli_password_mismatch(db):
    with pytest.raises(AppError) as info:
        cli.create_admin(
            reset_password=False,
            input_fn=_prompts(ADMIN_EMAIL),
            getpass_fn=_prompts(ADMIN_PASSWORD, ADMIN_PASSWORD + "x"),
            out=lambda _: None,
        )
    assert info.value.code == "PASSWORD_MISMATCH"
    assert auth_service.user_count(db) == 0


def test_cli_refuses_when_admin_exists(db, admin_user):
    out: list[str] = []
    code = cli.create_admin(reset_password=False, out=out.append)
    assert code == 1
    assert "--reset-password" in out[0]


def test_cli_reset_password_revokes_tokens(client, db, tokens):
    new_pw = "brand-new-password-9"
    code = cli.create_admin(
        reset_password=True, getpass_fn=_prompts(new_pw, new_pw), out=lambda _: None
    )
    assert code == 0
    assert login(client).status_code == 401
    assert login(client, password=new_pw).status_code == 200
    old = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == security.hash_refresh_token(tokens["refreshToken"])
        )
    )
    db.refresh(old)
    assert old.revoked_at is not None


def test_cli_reset_without_admin(db):
    assert cli.create_admin(reset_password=True, out=lambda _: None) == 1


def test_cli_main_reports_errors(db, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "bad-email")
    monkeypatch.setattr("getpass.getpass", lambda _: ADMIN_PASSWORD)
    assert cli.main(["create-admin"]) == 1
    assert "Email address is not valid" in capsys.readouterr().err


# --- first-start bootstrap ---------------------------------------------------------


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, jwt_secret=SECRET, **kw)


def test_bootstrap_creates_admin_once_and_never_logs_password(db, caplog):
    s = _settings(admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD)
    with caplog.at_level(logging.INFO):
        assert auth_service.bootstrap_admin(db, s) is True
        assert auth_service.bootstrap_admin(db, s) is False  # second start: ignored
    assert auth_service.user_count(db) == 1
    assert ADMIN_PASSWORD not in caplog.text
    assert "admin created" in caplog.text
    assert "ignored" in caplog.text


def test_bootstrap_noop_without_env(db):
    assert auth_service.bootstrap_admin(db, _settings(admin_email="", admin_password="")) is False
    assert auth_service.user_count(db) == 0
