"""Turbine classes: read-only lookups plus the sampled power/thrust curve."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.turbine_class import TurbineClass
from app.physics import power


@dataclass(frozen=True)
class CurvePoint:
    speed: float
    power_kw: float
    ct: float


def list_classes(db: Session) -> list[TurbineClass]:
    # Smallest to largest, the same order as the frontend's MODELS.
    return list(db.scalars(select(TurbineClass).order_by(TurbineClass.rated_kw)))


def get_class(db: Session, class_id: str) -> TurbineClass:
    cls = db.get(TurbineClass, class_id)
    if cls is None:
        raise NotFoundError(
            f"Turbine class '{class_id}' does not exist.",
            code="TURBINE_CLASS_NOT_FOUND",
            details={"id": class_id},
        )
    return cls


def power_curve(cls: TurbineClass, step: float) -> list[CurvePoint]:
    return [
        CurvePoint(speed=v, power_kw=power.power_kw(cls, v), ct=power.ct(cls, v))
        for v in power.curve_speeds(step)
    ]
