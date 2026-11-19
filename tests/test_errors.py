"""The unified error shape: {"error": {"code", "message", "details"}}."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import AppError, NotFoundError


class _Body(BaseModel):
    radius: int = Field(ge=500, le=6000)


@pytest.fixture
def err_client(app):
    router = APIRouter()

    @router.get("/_test/not-found")
    def not_found():
        raise NotFoundError("Site not found.", code="SITE_NOT_FOUND", details={"id": "x"})

    @router.get("/_test/conflict")
    def conflict():
        raise AppError("Already running.", code="ASSESSMENT_RUNNING", status_code=409)

    @router.post("/_test/validate")
    def validate(body: _Body):
        return body

    @router.get("/_test/boom")
    def boom():
        raise RuntimeError("secret internals")

    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _assert_shape(body: dict) -> dict:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]


def test_app_error(err_client):
    r = err_client.get("/_test/not-found")
    assert r.status_code == 404
    err = _assert_shape(r.json())
    assert err["code"] == "SITE_NOT_FOUND"
    assert err["details"] == {"id": "x"}


def test_app_error_custom_status(err_client):
    r = err_client.get("/_test/conflict")
    assert r.status_code == 409
    assert _assert_shape(r.json())["code"] == "ASSESSMENT_RUNNING"


def test_unknown_route_is_404_shape(err_client):
    r = err_client.get("/nope")
    assert r.status_code == 404
    assert _assert_shape(r.json())["code"] == "NOT_FOUND"


def test_wrong_method_is_405_shape(err_client):
    r = err_client.post("/health")
    assert r.status_code == 405
    assert _assert_shape(r.json())["code"] == "METHOD_NOT_ALLOWED"


def test_validation_error_lists_fields(err_client):
    r = err_client.post("/_test/validate", json={"radius": 400})
    assert r.status_code == 422
    err = _assert_shape(r.json())
    assert err["code"] == "VALIDATION_ERROR"
    assert err["details"]["fields"][0]["field"] == "radius"


def test_unhandled_error_hides_internals(err_client):
    r = err_client.get("/_test/boom")
    assert r.status_code == 500
    err = _assert_shape(r.json())
    assert err["code"] == "INTERNAL_ERROR"
    assert "secret" not in err["message"]
