"""Celery application — Redis broker/backend, with the periodic beat schedule."""
from celery import Celery

from app.core.config import get_settings
from app.workers.schedules import BEAT_SCHEDULE

settings = get_settings()

# Local dev (eager): use kombu's in-memory transport so Redis need not be
# installed or running. Production uses the real Redis broker/backend.
_eager = settings.CELERY_TASK_ALWAYS_EAGER
celery_app = Celery(
    "jobmatch",
    broker="memory://" if _eager else settings.REDIS_URL,
    backend="cache+memory://" if _eager else settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    beat_schedule=BEAT_SCHEDULE,
    # Local dev: run tasks inline in the calling process (no broker/worker).
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_TASK_ALWAYS_EAGER,
    task_store_eager_result=True,
)
