"""Dependency checks used by GET /health."""

import logging

import redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine
from app.schemas.health import ComponentStatus

logger = logging.getLogger(__name__)


def check_db() -> ComponentStatus:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT postgis_version()"))  # also proves PostGIS is installed
        return "ok"
    except Exception as exc:  # noqa: BLE001 - any failure means "down"
        logger.warning("health: database check failed", extra={"error": str(exc)})
        return "down"


def check_redis() -> ComponentStatus:
    try:
        client = redis.Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        try:
            client.ping()
        finally:
            client.close()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("health: redis check failed", extra={"error": str(exc)})
        return "down"
