"""Celery application setup — uses Redis as broker and result backend."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from celery.schedules import crontab


def _celery_url(kind: str) -> str:
    """Return the broker or result URL, falling back to the main Redis URL."""
    if kind == "broker":
        url = settings.celery_broker_url
    else:
        url = settings.celery_result_backend
    return url or settings.redis_url


def create_celery_app() -> Celery:
    """Create and configure the Celery application."""

    broker_url = _celery_url("broker")
    result_backend = _celery_url("backend")

    app = Celery(
        "caiwu",
        broker=broker_url,
        backend=result_backend,
    )

    app.conf.update(
        # Task queues
        task_queues={
            "default": {"exchange": "default", "routing_key": "default"},
            "report_generation": {"exchange": "report_generation", "routing_key": "report_generation"},
            "prediction": {"exchange": "prediction", "routing_key": "prediction"},
            "notification": {"exchange": "notification", "routing_key": "notification"},
            "data_sync": {"exchange": "data_sync", "routing_key": "data_sync"},
            "ai_inference": {"exchange": "ai_inference", "routing_key": "ai_inference"},
            "email_poll": {"exchange": "email_poll", "routing_key": "email_poll"},
            "cache_warm": {"exchange": "cache_warm", "routing_key": "cache_warm"},
        },
        task_default_queue="default",
        task_routes={
            "app.tasks.report_gen.*": {"queue": "report_generation"},
            "app.tasks.prediction.*": {"queue": "prediction"},
            "app.tasks.notification.*": {"queue": "notification"},
            "app.tasks.email_poll.*": {"queue": "email_poll"},
        },
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        # Acknowledgement
        task_acks_late=True,
        # Timeouts
        task_soft_time_limit=settings.report_generator_timeout_seconds,
        task_time_limit=settings.report_generator_timeout_seconds + 60,
        # Retries
        task_max_retries=settings.report_max_retries,
        task_default_retry_delay=30,
        task_default_retry_backoff=True,
        task_default_retry_backoff_max=300,
        # Concurrency
        worker_prefetch_multiplier=1,
        # Result expiry
        result_expires=3600,
        # Beat schedule — daily email poll at 02:00 local time
        beat_schedule={
            "daily-email-poll": {
                "task": "email_poll.poll_emails",
                "schedule": crontab(hour=settings.email_poll_hour, minute=settings.email_poll_minute),
            },
            "daily-rule-audit": {
                "task": "rule_audit.audit_all_rules",
                "schedule": crontab(hour=3, minute=0),  # daily at 03:00
            },
            "daily-dimension-sync": {
                "task": "dim_sync.sync_all_dimensions",
                "schedule": crontab(hour=4, minute=0),  # daily at 04:00
            },
        },
    )

    app.autodiscover_tasks(["app.tasks"], force=True)

    return app


celery_app = create_celery_app()
