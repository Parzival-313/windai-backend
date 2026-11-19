import os

import pytest

from app import __version__
from app.services import health_service


def _patch(monkeypatch, db: str, redis: str) -> None:
    monkeypatch.setattr(health_service, "check_db", lambda: db)
    monkeypatch.setattr(health_service, "check_redis", lambda: redis)


def test_health_all_ok(client, monkeypatch):
    _patch(monkeypatch, "ok", "ok")
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "redis": "ok", "version": __version__}


@pytest.mark.parametrize(("db", "redis"), [("ok", "down"), ("down", "ok"), ("down", "down")])
def test_health_degraded_returns_503(client, monkeypatch, db, redis):
    _patch(monkeypatch, db, redis)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["db"] == db
    assert r.json()["redis"] == redis


def test_health_needs_no_auth_and_sets_request_id(client, monkeypatch):
    _patch(monkeypatch, "ok", "ok")
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


@pytest.mark.skipif(os.getenv("SKIP_INTEGRATION") == "1", reason="needs real db + redis")
def test_health_live_dependencies(client):
    """Runs against the real Postgres/PostGIS and Redis (inside docker compose)."""
    r = client.get("/health")
    assert r.json()["db"] == "ok", "Postgres/PostGIS not reachable"
    assert r.json()["redis"] == "ok", "Redis not reachable"
