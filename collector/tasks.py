import asyncio
import logging
from datetime import datetime, timezone
from celery.exceptions import SoftTimeLimitExceeded

from .celery_app import celery_app
from .resolver_v2 import resolve_youtube_channel_id
from .yt_client import get_yt_client
from .state import STATE

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def finalize_run_task(self, run_id: int):
    """
    Асинхронная задача для вызова логики финализации Run.
    """
    from .orchestrator import Orchestrator # Импортируем здесь, чтобы избежать цикла
    logger.info(f"Attempting to finalize Run {run_id}.")
    orchestrator = Orchestrator()
    try:
        finalized = orchestrator.finalize_run(run_id)
        if finalized:
            logger.info(f"Run {run_id} was successfully finalized.")
        else:
            logger.info(f"Run {run_id} is not yet ready to be finalized.")
    except Exception as e:
        logger.exception(f"An error occurred while trying to finalize Run {run_id}: {e}")

# Устанавливаем soft time limit в 60 секунд.
@celery_app.task(bind=True, soft_time_limit=60)
def process_channel_job(self, job_id: int, run_id: int):
    """
    Синхронная Celery-задача, которая запускает асинхронную логику внутри.
    """
    async def _async_process():
        logger.info(f"Starting to process Job {job_id} for Run {run_id}.")

        job = STATE.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in state. Aborting.")
            return

        run = STATE.get_run(run_id)
        if not run:
            logger.error(f"Run {run_id} for Job {job_id} not found. Aborting.")
            return

        job.status = "PROCESSING"
        job.updated_at = datetime.now(timezone.utc)
        STATE.update_job(job)

        try:
            client = get_yt_client()
            result = await resolve_youtube_channel_id(
                input_str=job.input_channel,
                owner_id=run.owner_id,
                youtube_client=client
            )

            job.updated_at = datetime.now(timezone.utc)
            if result.youtube_channel_id:
                job.status = "DONE"
                job.youtube_channel_id = result.youtube_channel_id
            elif result.needs_search_fallback:
                job.status = "NEEDS_SEARCH"
                job.last_error = "Needs expensive search fallback"
            else:
                job.status = "FAILED"
                job.last_error = result.error

            STATE.update_job(job)
            logger.info(f"Job {job_id} finished with status {job.status}.")

        finally:
            # This block will run even if the async logic has an exception.
            # We must ensure the finalizer is always called.
            pass


    try:
        asyncio.run(_async_process())

    except SoftTimeLimitExceeded:
        logger.warning(f"Job {job_id} exceeded its TTL.")
        job.status = "FAILED"
        job.last_error = "TTL exceeded"
        job.updated_at = datetime.now(timezone.utc)
        STATE.update_job(job)
        self.update_state(state='FAILURE', meta={'exc': 'SoftTimeLimitExceeded'})

    except Exception as e:
        logger.exception(f"An unexpected error occurred in Job {job_id}: {e}")
        job.status = "FAILED"
        job.last_error = str(e)
        job.updated_at = datetime.now(timezone.utc)
        STATE.update_job(job)
        self.update_state(state='FAILURE', meta={'exc': str(e)})

    finally:
        finalize_run_task.delay(run_id)
