from celery import Celery
from .config import settings

celery_app = Celery(
    "competitor_analysis_collector",
    broker=settings.broker_url,
    include=["collector.tasks"]
)

# Broker settings for connection pooling
celery_app.conf.broker_pool_limit = 10

# Disable result backend and apply recommended settings for reliability
celery_app.conf.update(
    task_ignore_result=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
