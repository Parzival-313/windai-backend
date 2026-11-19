"""Shared pytest fixtures.

Env vars are set *before* the app is imported, so Settings validation passes.
Inside Docker, DATABASE_URL/REDIS_URL already point at the compose services and
are left untouched.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5500")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    # raise_server_exceptions=False lets us assert on the 500 error shape.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
