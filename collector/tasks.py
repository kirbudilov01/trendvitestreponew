import logging
from .celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def process_channel_job(self, job_id: int):
    """
    Основная задача для обработки одного YouTube-канала (Job).
    На данном этапе это просто скелет.
    """
    logger.info(f"Starting to process job_id: {job_id}")
    # Логика будет добавлена в следующих PR
    logger.info(f"Successfully finished processing job_id: {job_id}")
    return {"job_id": job_id, "status": "COMPLETED_SKELETON"}
