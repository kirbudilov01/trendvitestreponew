from celery import Celery
from .config import settings

celery_app = Celery(
    "competitor_analysis_collector",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["collector.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
)
