"""Celery Beat schedule for the continuous-alerts + maintenance pipeline."""
from celery.schedules import crontab

BEAT_SCHEDULE = {
    "run-daily-alerts": {
        "task": "run_subscriptions",
        "schedule": crontab(hour=8, minute=0),       # 08:00 UTC daily
        "args": ("daily",),
    },
    "run-weekly-alerts": {
        "task": "run_subscriptions",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),  # Mondays 08:00 UTC
        "args": ("weekly",),
    },
    "deactivate-stale-jobs": {
        "task": "deactivate_stale_jobs",
        "schedule": crontab(hour=3, minute=0),       # 03:00 UTC daily
        "args": (30,),
    },
}
