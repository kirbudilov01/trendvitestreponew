import asyncio
import logging
from datetime import datetime, timezone
from celery.exceptions import SoftTimeLimitExceeded

from .celery_app import celery_app
from .resolver_v2 import resolve_youtube_channel_id
from .yt_client import get_yt_client
from .state import STATE
from .redis_client import shared_redis_client

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def finalize_run_task(self, run_id: int):
    """
    Synchronous task to finalize a Run.
    """
    from .orchestrator import Orchestrator
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

async def process_channel_job_async(job_id: int, run_id: int):
    """
    Asynchronous worker containing the core logic for processing a single channel.
    """
    job = STATE.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found in state at start. Aborting.")
        return

    try:
        logger.info(f"Starting async processing for Job {job_id} in Run {run_id}.")

        run = STATE.get_run(run_id)
        if not run:
            logger.error(f"Run {run_id} for Job {job_id} not found. Aborting.")
            return

        job.status = "PROCESSING"
        job.updated_at = datetime.now(timezone.utc)
        STATE.update_job(job)

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

    except asyncio.CancelledError:
        logger.warning(f"Job {job_id} was cancelled (likely due to TTL).")
        job.status = "FAILED"
        job.last_error = "Task cancelled or TTL exceeded"
        job.updated_at = datetime.now(timezone.utc)
        STATE.update_job(job)
        raise  # Re-raise the exception so Celery can handle it.


@celery_app.task(bind=True, soft_time_limit=60)
def process_channel_job(self, job_id: int, run_id: int):
    """
    Synchronous Celery task wrapper that executes the async worker.
    This pattern ensures reliable execution in Celery.
    """
    try:
        # We move the finalizer call into the async task to ensure it runs
        # even if the task is cancelled.
        asyncio.run(process_channel_job_async(job_id, run_id))

    except (SoftTimeLimitExceeded, asyncio.CancelledError):
        logger.warning(f"Job {job_id} exceeded its time limit.")
        # The async task already updated the job status.
        # We just need to inform Celery about the failure.
        self.update_state(state='FAILURE', meta={'exc': 'TimeLimitExceeded'})

    except Exception as e:
        logger.exception(f"An unexpected error occurred in Job {job_id}: {e}")
        job = STATE.get_job(job_id)
        if job:
            job.status = "FAILED"
            job.last_error = str(e)
            job.updated_at = datetime.now(timezone.utc)
            STATE.update_job(job)
        self.update_state(state='FAILURE', meta={'exc': str(e)})

    finally:
        # The finalizer is now always called from within the async worker's finally block.
        pass
