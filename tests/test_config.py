import pytest
from pydantic import ValidationError

from app.core.config import Settings

SECRET = "s" * 40


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, jwt_secret=SECRET, **overrides)


def test_cors_origins_split_from_comma_string():
    s = _settings(cors_origins="http://a.test, http://b.test")
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_wildcard_rejected():
    with pytest.raises(ValidationError):
        _settings(cors_origins="*")


def test_short_jwt_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret="short")


def test_missing_jwt_secret_rejected(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_plain_postgres_url_uses_psycopg_driver():
    s = _settings(database_url="postgresql://u:p@h:5432/d")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/d"
