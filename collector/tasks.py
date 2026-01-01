import logging
from datetime import datetime, timezone

from .celery_app import celery_app
from .redis_client import redis_client
from .resolver import resolve_youtube_channel, ResolveStatus
from .yt.client import YouTubeClient
from .state import STATE


logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def finalize_run_task(self, run_id: int):
    """
    Асинхронная задача для вызова логики финализации Run.
    """
    lock_key = f"finalize_run_lock:{run_id}"
    lock = redis_client.lock(lock_key, timeout=60)

    if not lock.acquire(blocking=False):
        logger.info(f"Finalization for Run {run_id} is already in progress. Skipping.")
        return

    try:
        from .orchestrator import Orchestrator # Импортируем здесь, чтобы избежать цикла
        logger.info(f"Attempting to finalize Run {run_id}.")
        orchestrator = Orchestrator()
        finalized = orchestrator.finalize_run(run_id)
        if finalized:
            logger.info(f"Run {run_id} was successfully finalized.")
        else:
            logger.info(f"Run {run_id} is not yet ready to be finalized.")
    except Exception as e:
        logger.exception(f"An error occurred while trying to finalize Run {run_id}: {e}")
    finally:
        lock.release()

@celery_app.task(bind=True, soft_time_limit=900, time_limit=1200)  # 15 min soft, 20 min hard
def process_channel_job(self, job_id: int, run_id: int):
    """
    Основная задача для обработки одного Job, теперь с обновлением состояния.
    """
    logger.info(f"Starting to process Job {job_id} for Run {run_id}.")

    job = STATE.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found in state. Aborting.")
        return

    # 1. Обновляем статус на PROCESSING
    job.status = "PROCESSING"
    job.updated_at = datetime.now(timezone.utc)
    STATE.update_job(job)

    try:
        client = YouTubeClient()
        result = resolve_youtube_channel(job.input_channel, client)

        # 2. Обновляем Job с результатом
        job.updated_at = datetime.now(timezone.utc)
        if result.status == ResolveStatus.RESOLVED:
            job.status = "DONE"
            job.youtube_channel_id = result.youtube_channel_id
        else:
            job.status = "FAILED"
            job.last_error = result.reason

        STATE.update_job(job)
        logger.info(f"Job {job_id} finished with status {job.status}.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred in Job {job_id}: {e}")
        # Обновляем Job с информацией об ошибке
        job.status = "FAILED"
        job.last_error = str(e)
        job.updated_at = datetime.now(timezone.utc)
        STATE.update_job(job)
        self.update_state(state='FAILURE', meta={'exc': str(e)})

    finally:
        # 3. После каждой джобы пытаемся финализировать Run
        finalize_run_task.apply_async(args=[run_id], countdown=5)
