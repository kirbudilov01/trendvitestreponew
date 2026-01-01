from celery import Celery
from .config import settings

celery_app = Celery(
    "competitor_analysis_collector",
    broker=settings.broker_url,
    include=["collector.tasks"]
)

celery_app.conf.update(
    # Core settings for production stability
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,

    # Keep this for visibility into running tasks
    task_track_started=True,
)
