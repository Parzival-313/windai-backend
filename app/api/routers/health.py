from fastapi import APIRouter, Response, status

from app import __version__
from app.schemas.health import HealthOut
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Service health (no auth)",
    responses={503: {"model": HealthOut, "description": "A dependency is down"}},
)
def health(response: Response) -> HealthOut:
    db = health_service.check_db()
    rds = health_service.check_redis()
    healthy = db == "ok" and rds == "ok"
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(status="ok" if healthy else "degraded", db=db, redis=rds, version=__version__)
