import logging
from .celery_app import celery_app
from .resolver import resolve_youtube_channel
from .youtube_client import YouTubeClient
from .models import Job  # Assuming Job model is used to fetch job details

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def process_channel_job(self, job_id: int, input_channel_str: str):
    """
    Основная задача для обработки одного YouTube-канала (Job).
    На данном этапе она инициализирует клиент, вызывает резолвер и логирует результат.
    """
    logger.info(f"Starting to process job_id: {job_id} for input: '{input_channel_str}'")

    try:
        # В реальной имплементации Job-объект будет загружаться из базы.
        # job = Job.get(id=job_id)
        # input_channel_str = job.input_channel

        # Инициализация YouTube клиента. В будущем ключи будут передаваться умнее.
        client = YouTubeClient()

        # Вызов резолвера
        result = resolve_youtube_channel(input_channel_str, client)

        # Логирование результата
        logger.info(f"Job ID {job_id} resolved with status '{result.status}'. "
                    f"Channel ID: {result.youtube_channel_id}. Reason: {result.reason}")

        # Здесь в будущем будет обновление статуса Job в базе данных.
        # job.status = result.status
        # job.youtube_channel_id = result.youtube_channel_id
        # job.save()

        return result.dict()

    except Exception as e:
        logger.exception(f"An unexpected error occurred in job_id {job_id}: {e}")
        # Здесь будет логика для обработки сбоев: обновление статуса, retry и т.д.
        # job.status = "FAILED"
        # job.last_error = str(e)
        # job.save()
        self.update_state(state='FAILURE', meta={'exc': str(e)})
        raise
