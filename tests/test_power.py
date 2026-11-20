"""Unit tests for app/physics/power.py (no database).

Parity: `power_kw` must give the frontend's `powerKW` result for every class and speed in
tests/fixtures/turbine_classes_js.json, which Node produced from the frontend's own code.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.physics.power import CT_MIN, ct, curve_speeds, power_kw

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/turbine_classes_js.json").read_text("utf-8"))


@dataclass(frozen=True)
class Spec:
    v_in: float
    v_rated: float
    v_out: float
    rated_kw: float


def _spec(class_id: str) -> Spec:
    m = FIXTURE["models"][class_id]
    return Spec(v_in=m["vin"], v_rated=m["vr"], v_out=m["vout"], rated_kw=m["rated"])


G45 = _spec("g45")


def test_fixture_matches_current_frontend_code():
    """Fails if MODELS/powerKW in the frontend changed after the fixture was generated."""
    html = (ROOT / FIXTURE["source"]).read_text("utf-8").replace("\r\n", "\n")
    start = html.index("const MODELS = {")
    end = html.index("function rotorRPM(", start)
    digest = hashlib.sha256(html[start:end].encode("utf-8")).hexdigest()
    assert digest == FIXTURE["sourceSha256"], (
        "frontend turbine code changed: run `node tests/fixtures/make_turbine_fixture.mjs` "
        "and add a migration if MODELS values changed"
    )


@pytest.mark.parametrize("class_id", ["g36", "g45", "g62"])
def test_power_kw_matches_frontend_js(class_id):
    spec = _spec(class_id)
    points = FIXTURE["powerKw"][class_id]
    assert len(points) > 100
    for p in points:
        assert power_kw(spec, p["speed"]) == pytest.approx(p["powerKw"], rel=1e-12, abs=1e-9), p


@pytest.mark.parametrize(
    ("v", "expected"),
    [
        (0.0, 0.0),
        (2.99, 0.0),
        (3.0, 0.0),  # v_in: the cubic term is exactly zero
        (7.0, 4500 * (7**3 - 3**3) / (11**3 - 3**3)),  # 1090.49 kW
        (11.0, 4500.0),  # rated speed
        (24.99, 4500.0),
        (25.0, 0.0),  # cut-out
        (30.0, 0.0),
        (-1.0, 0.0),
    ],
)
def test_power_kw_g45_hand_values(v, expected):
    assert power_kw(G45, v) == pytest.approx(expected)


def test_power_kw_nan_is_zero():
    assert power_kw(G45, math.nan) == 0.0


def test_power_kw_is_monotonic_between_cut_in_and_rated():
    values = [power_kw(G45, 3 + i * 0.01) for i in range(801)]  # 3 … 11 m/s
    assert all(b >= a for a, b in zip(values, values[1:], strict=False))


@pytest.mark.parametrize(
    ("v", "expected"),
    [
        (2.99, 0.0),  # below cut-in: rotor parked
        (3.0, 0.8),  # operating from v_in (same boundary as the power curve)
        (7.0, 0.8),
        (11.0, 0.8),  # rated: both branches agree
        (12.0, 0.8 * (11 / 12) ** 3),
        (24.99, 0.8 * (11 / 24.99) ** 3),
        (25.0, 0.0),  # cut-out
        (-1.0, 0.0),
    ],
)
def test_ct_g45(v, expected):
    assert ct(G45, v) == pytest.approx(expected)


def test_ct_nan_is_zero():
    assert ct(G45, math.nan) == 0.0


def test_ct_never_below_minimum_while_operating():
    # The real classes never reach the floor before 25 m/s; a synthetic one with a high
    # cut-out does: 0.8 * (10/40)^3 = 0.0125 -> clamped to 0.05.
    spec = Spec(v_in=3, v_rated=10, v_out=50, rated_kw=1000)
    assert ct(spec, 40) == CT_MIN
    assert all(ct(_spec(c), v) >= CT_MIN for c in ("g36", "g45", "g62") for v in (12, 20, 24.9))


def test_curve_speeds_default_step():
    speeds = curve_speeds(0.5)
    assert len(speeds) == 61
    assert speeds[0] == 0.0 and speeds[-1] == 30.0


def test_curve_speeds_have_no_float_noise():
    speeds = curve_speeds(0.1)
    assert len(speeds) == 301
    assert speeds[3] == 0.3
    assert speeds[-1] == 30.0


def test_curve_speeds_stop_below_max_when_not_a_multiple():
    assert curve_speeds(0.7)[-1] == 29.4


@pytest.mark.parametrize("bad", [0.0, -0.5, math.nan, math.inf])
def test_curve_speeds_rejects_bad_step(bad):
    with pytest.raises(ValueError):
        curve_speeds(bad)
