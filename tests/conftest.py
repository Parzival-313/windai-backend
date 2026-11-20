"""Shared pytest fixtures.

Env vars are set *before* the app is imported, so Settings validation passes.

Database: tests ALWAYS use TEST_DATABASE_URL (a separate `<db>_test` database in the
local Docker `db` container, set by docker-compose) — never DATABASE_URL, which may
point at Neon. A guard refuses anything that is not a local `*_test` database,
because the fixtures truncate every table.
"""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

_DEFAULT_TEST_DB = "postgresql+psycopg://aeolus:aeolus@localhost:5433/aeolus_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _DEFAULT_TEST_DB

_url = make_url(TEST_DATABASE_URL)
if not (_url.database or "").endswith("_test") or _url.host not in {"db", "localhost", "127.0.0.1"}:
    raise RuntimeError(
        f"Refusing to run tests against {_url.host}/{_url.database}: "
        "TEST_DATABASE_URL must be a local database whose name ends in _test."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # overrides .env (env vars win over the file)
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5500")
os.environ["ADMIN_EMAIL"] = ""  # never bootstrap an admin from the developer's .env
os.environ["ADMIN_PASSWORD"] = ""
os.environ["LOGIN_RATE_LIMIT"] = "5/minute"

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import auth_service  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()
    yield


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    # raise_server_exceptions=False lets us assert on the 500 error shape.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --- database ----------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_database() -> str:
    """Create the test database if needed and migrate it to head (once per run)."""
    admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_url.database}"'))
    admin.dispose()

    # Run Alembic in a subprocess: same code path as the API container, and it keeps
    # Alembic's logging config out of the test process.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True,
        capture_output=True,
    )
    return TEST_DATABASE_URL


@pytest.fixture
def db(test_database):
    """A session on a freshly emptied test database.

    Tables marked `info={"seeded": True}` (reference data inserted by migrations, e.g.
    `turbine_classes`) are kept: nothing in the tests re-creates them.
    """
    tables = ", ".join(
        f'"{t.name}"' for t in Base.metadata.sorted_tables if not t.info.get("seeded")
    )
    session = get_sessionmaker()()
    session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db):
    return auth_service.create_admin(db, ADMIN_EMAIL, ADMIN_PASSWORD)


def login(client, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture
def tokens(client, admin_user) -> dict:
    r = login(client)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def auth_headers(tokens) -> dict:
    return {"Authorization": f"Bearer {tokens['accessToken']}"}
