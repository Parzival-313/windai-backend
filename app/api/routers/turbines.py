"""`/api/v1/turbine-classes` — the generic turbine classes and their power curves.

Read-only: the classes are reference data seeded by migration `0003`.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.turbines import PowerCurvePointOut, TurbineClassOut
from app.services import turbine_service

router = APIRouter(prefix="/turbine-classes", tags=["turbines"])

_401 = {401: {"description": "Not authenticated / invalid token"}}
_404 = {404: {"description": "Unknown turbine class id (TURBINE_CLASS_NOT_FOUND)"}}

STEP_MIN = 0.1
STEP_MAX = 5.0


@router.get(
    "",
    response_model=list[TurbineClassOut],
    summary="List turbine classes (smallest first)",
    responses=_401,
)
def list_turbine_classes(_user: CurrentUser, db: DbSession) -> list[TurbineClassOut]:
    return [TurbineClassOut.model_validate(c) for c in turbine_service.list_classes(db)]


@router.get(
    "/{class_id}",
    response_model=TurbineClassOut,
    summary="Get one turbine class",
    responses={**_401, **_404},
)
def get_turbine_class(class_id: str, _user: CurrentUser, db: DbSession) -> TurbineClassOut:
    return TurbineClassOut.model_validate(turbine_service.get_class(db, class_id))


@router.get(
    "/{class_id}/power-curve",
    response_model=list[PowerCurvePointOut],
    summary="Power and thrust curve sampled from 0 to 30 m/s",
    responses={**_401, **_404},
)
def get_power_curve(
    class_id: str,
    _user: CurrentUser,
    db: DbSession,
    step: Annotated[
        float,
        Query(ge=STEP_MIN, le=STEP_MAX, description="Speed step in m/s (0.1–5)."),
    ] = 0.5,
) -> list[PowerCurvePointOut]:
    cls = turbine_service.get_class(db, class_id)
    return [
        PowerCurvePointOut(speed=p.speed, power_kw=p.power_kw, ct=p.ct)
        for p in turbine_service.power_curve(cls, step)
    ]
