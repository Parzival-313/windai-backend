"""API tests for /api/v1/turbine-classes against the local test database.

The expected class values come from tests/fixtures/turbine_classes_js.json, i.e. from the
frontend's own `MODELS` object, not from a second hand-typed copy.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.turbine_class import TurbineClass

BASE = "/api/v1/turbine-classes"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/turbine_classes_js.json").read_text("utf-8"))
MODELS = FIXTURE["models"]


def _err(r) -> dict:
    body = r.json()
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]


# --- auth --------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["", "/g45", "/g45/power-curve", "/nope"])
def test_every_endpoint_requires_auth(client, db, path):
    r = client.get(BASE + path)
    assert r.status_code == 401
    assert _err(r)["code"] == "NOT_AUTHENTICATED"


def test_invalid_token_rejected(client, db):
    r = client.get(BASE, headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert _err(r)["code"] == "INVALID_TOKEN"


# --- seed data ---------------------------------------------------------------------


def test_migration_seeds_three_classes_and_tests_keep_them(db):
    ids = list(db.scalars(select(TurbineClass.id).order_by(TurbineClass.id)))
    assert ids == ["g36", "g45", "g62"]


# --- list / get --------------------------------------------------------------------


def test_list_returns_frontend_models_exactly(client, auth_headers):
    r = client.get(BASE, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert [c["id"] for c in body] == ["g36", "g45", "g62"]  # same order as MODELS
    assert body == list(MODELS.values())


@pytest.mark.parametrize("class_id", ["g36", "g45", "g62"])
def test_get_one_returns_frontend_model(client, auth_headers, class_id):
    r = client.get(f"{BASE}/{class_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == MODELS[class_id]


def test_response_uses_frontend_field_names(client, auth_headers):
    body = client.get(f"{BASE}/g45", headers=auth_headers).json()
    assert set(body) == {"id", "name", "D", "H", "rated", "vin", "vr", "vout", "rpmMin", "rpmMax"}


@pytest.mark.parametrize("class_id", ["g99", "G45", "x" * 40])
def test_unknown_class_is_404(client, auth_headers, class_id):
    r = client.get(f"{BASE}/{class_id}", headers=auth_headers)
    assert r.status_code == 404
    err = _err(r)
    assert err["code"] == "TURBINE_CLASS_NOT_FOUND"
    assert err["details"] == {"id": class_id}


# --- power curve -------------------------------------------------------------------


def test_power_curve_default_step(client, auth_headers):
    r = client.get(f"{BASE}/g45/power-curve", headers=auth_headers)
    assert r.status_code == 200
    points = r.json()
    assert len(points) == 61
    assert set(points[0]) == {"speed", "powerKw", "ct"}
    assert points[0]["speed"] == 0 and points[-1]["speed"] == 30


@pytest.mark.parametrize("class_id", ["g36", "g45", "g62"])
def test_power_curve_matches_frontend_js(client, auth_headers, class_id):
    js = {p["speed"]: p["powerKw"] for p in FIXTURE["powerKw"][class_id]}
    points = client.get(f"{BASE}/{class_id}/power-curve", headers=auth_headers).json()
    for p in points:  # every 0.5 m/s step is in the fixture
        assert p["powerKw"] == pytest.approx(js[p["speed"]], rel=1e-12, abs=1e-9), p


def test_power_curve_g45_spot_values(client, auth_headers):
    """The design's manual check: g45 at 3, 7, 11 and 25 m/s."""
    points = client.get(f"{BASE}/g45/power-curve", headers=auth_headers).json()
    by_speed = {p["speed"]: p for p in points}
    assert by_speed[3]["powerKw"] == 0
    assert by_speed[7]["powerKw"] == pytest.approx(1090.4907975460123)
    assert by_speed[11]["powerKw"] == 4500
    assert by_speed[25]["powerKw"] == 0
    assert by_speed[3]["ct"] == 0.8
    assert by_speed[12]["ct"] == pytest.approx(0.8 * (11 / 12) ** 3)
    assert by_speed[25]["ct"] == 0


def test_power_curve_custom_step(client, auth_headers):
    r = client.get(f"{BASE}/g62/power-curve", params={"step": 0.1}, headers=auth_headers)
    assert r.status_code == 200
    speeds = [p["speed"] for p in r.json()]
    assert len(speeds) == 301
    assert speeds[3] == 0.3


@pytest.mark.parametrize("step", ["0", "0.05", "5.5", "-1", "abc"])
def test_power_curve_rejects_bad_step(client, auth_headers, step):
    r = client.get(f"{BASE}/g45/power-curve", params={"step": step}, headers=auth_headers)
    assert r.status_code == 422
    err = _err(r)
    assert err["code"] == "VALIDATION_ERROR"
    assert err["details"]["fields"][0]["field"] == "query.step"


def test_power_curve_unknown_class_is_404(client, auth_headers):
    r = client.get(f"{BASE}/g99/power-curve", headers=auth_headers)
    assert r.status_code == 404
    assert _err(r)["code"] == "TURBINE_CLASS_NOT_FOUND"
