"""Turbine-class responses.

Field names in JSON are the frontend's own `MODELS` keys (`D`, `H`, `rated`, `vin`, `vr`,
`vout`, `rpmMin`, `rpmMax`), so in Step 9 the browser can use the API objects in place of
its hard-coded `MODELS` without renaming anything. Python keeps descriptive snake_case
names; `alias=` maps them (like a Go struct tag `json:"D"`).
"""

from pydantic import ConfigDict, Field

from app.schemas.base import CamelModel


class TurbineClassOut(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(examples=["g45"])
    name: str = Field(examples=["4.5 MW class"])
    rotor_d_m: int = Field(alias="D", description="Rotor diameter (m).", examples=[145])
    hub_h_m: int = Field(alias="H", description="Hub height (m).", examples=[105])
    rated_kw: int = Field(alias="rated", description="Rated power (kW).", examples=[4500])
    v_in: float = Field(alias="vin", description="Cut-in wind speed (m/s).", examples=[3])
    v_rated: float = Field(alias="vr", description="Rated wind speed (m/s).", examples=[11])
    v_out: float = Field(alias="vout", description="Cut-out wind speed (m/s).", examples=[25])
    rpm_min: float = Field(description="Minimum rotor speed (rpm).", examples=[4.8])
    rpm_max: float = Field(description="Maximum rotor speed (rpm).", examples=[12.3])


class PowerCurvePointOut(CamelModel):
    speed: float = Field(description="Hub-height wind speed (m/s).")
    power_kw: float = Field(description="Electrical power (kW), same formula as the frontend.")
    ct: float = Field(description="Thrust coefficient used by the wake model (assumption).")
