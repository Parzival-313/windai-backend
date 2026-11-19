from typing import Literal

from app.schemas.base import CamelModel

ComponentStatus = Literal["ok", "down"]


class HealthOut(CamelModel):
    status: Literal["ok", "degraded"]
    db: ComponentStatus
    redis: ComponentStatus
    version: str
