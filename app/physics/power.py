"""Turbine power and thrust curves (design §6). Pure functions, no I/O.

`power_kw` is a line-for-line port of `powerKW` in `frontend/AeolusAi.html`:

    P(v) = 0                                          if v < v_in or v >= v_out (or v is NaN)
         = rated                                      if v >= v_rated
         = rated * (v³ - v_in³) / (v_rated³ - v_in³)  otherwise

`ct` is the generic thrust coefficient for the wake model (an assumption, not frontend
behaviour): 0.8 between cut-in and rated, then 0.8 * (v_rated / v)³ (never below 0.05)
up to cut-out, 0 outside the operating range. "Operating" uses the same boundaries as the
power curve: v_in <= v < v_out.

Both take any object with `v_in`, `v_rated`, `v_out`, `rated_kw` attributes — the ORM
`TurbineClass` row, or a small dataclass in tests (Go analogy: an interface satisfied
implicitly by any struct with those fields).
"""

import math
from typing import Protocol

CT_OPERATING = 0.8
CT_MIN = 0.05
CURVE_MAX_SPEED = 30.0  # m/s, upper end of GET /turbine-classes/{id}/power-curve


class TurbineCurve(Protocol):
    @property
    def v_in(self) -> float: ...
    @property
    def v_rated(self) -> float: ...
    @property
    def v_out(self) -> float: ...
    @property
    def rated_kw(self) -> float: ...


def _operating(cls: TurbineCurve, v: float) -> bool:
    # Any comparison with NaN is False, so NaN is "not operating" — same as the JS `!(v >= m.vin)`.
    return v >= cls.v_in and v < cls.v_out


def power_kw(cls: TurbineCurve, v: float) -> float:
    """Electrical power (kW) at hub-height wind speed `v` (m/s)."""
    if not _operating(cls, v):
        return 0.0
    if v >= cls.v_rated:
        return float(cls.rated_kw)
    return cls.rated_kw * (v**3 - cls.v_in**3) / (cls.v_rated**3 - cls.v_in**3)


def ct(cls: TurbineCurve, v: float) -> float:
    """Thrust coefficient (dimensionless) at hub-height wind speed `v` (m/s)."""
    if not _operating(cls, v):
        return 0.0
    if v <= cls.v_rated:
        return CT_OPERATING
    return max(CT_OPERATING * (cls.v_rated / v) ** 3, CT_MIN)


def curve_speeds(step: float, max_speed: float = CURVE_MAX_SPEED) -> list[float]:
    """0, step, 2·step, … up to and including `max_speed` when it is a multiple of `step`.

    Speeds are computed as i·step (not by repeated addition) and rounded, so 0.1-steps give
    0.3 rather than 0.30000000000000004.
    """
    if not (step > 0 and math.isfinite(step)):
        raise ValueError("step must be a positive finite number")
    n = math.floor(max_speed / step + 1e-9)
    return [round(i * step, 6) for i in range(n + 1)]
