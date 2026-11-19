"""Celery application (the background worker).

Celery is roughly a job queue + worker pool: the API pushes a message onto Redis
(`task.delay(...)`), and the separate `worker` container pulls it and runs the
function. In Step 6 this runs the assessment pipeline; for now it only has `ping`.

Start a worker: celery -A app.worker.celery_app worker --loglevel=INFO
"""

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery("aeolus", broker=_settings.redis_url, backend=_settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # a job is only removed from the queue after it finishes
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="aeolus.ping")
def ping() -> str:
    """No-op task to prove the API -> Redis -> worker path works."""
    return "pong"
