import logging
from typing import List, Dict, Any
import itertools

from .models import Run, Job
from .tasks import process_channel_job

logger = logging.getLogger(__name__)

# Используем itertools.count для генерации временных, уникальных ID в пределах одного запуска.
# В реальной системе это будут авто-инкрементные ID из базы данных.
_job_id_counter = itertools.count(start=1)
_run_id_counter = itertools.count(start=1)


class RunManager:
    """
    Управляет созданием и запуском анализа (Run) и связанных с ним задач (Job).
    """
    def start_analysis(self, analysis_id: int, owner_id: int, channel_inputs: List[str]) -> Dict[str, Any]:
        """
        Создает Run, Job'ы и запускает Celery-задачи для каждого канала.

        Returns:
            Словарь с информацией о созданном Run и количестве запущенных задач.
        """
        if not channel_inputs:
            logger.warning(f"Analysis {analysis_id} requested with no channel inputs. Nothing to do.")
            return {"run_id": None, "jobs_created": 0, "message": "No inputs provided."}

        # 1. Создаем объект Run (концептуально)
        run_id = next(_run_id_counter)
        run = Run(id=run_id, analysis_id=analysis_id, owner_id=owner_id, status="PROCESSING")
        logger.info(f"Created Run {run.id} for analysis {analysis_id}.")

        # 2. Создаем и запускаем Job'ы
        jobs_launched = 0
        for channel_input in channel_inputs:
            if not channel_input or not channel_input.strip():
                logger.warning(f"Skipping empty channel input for Run {run.id}.")
                continue

            # Создаем объект Job (концептуально)
            job_id = next(_job_id_counter)
            job = Job(id=job_id, run_id=run.id, input_channel=channel_input)
            run.jobs.append(job)

            # Запускаем Celery-задачу
            try:
                process_channel_job.delay(job_id=job.id, input_channel_str=job.input_channel)
                logger.info(f"Launched Celery task for Job {job.id} with input '{job.input_channel}'.")
                jobs_launched += 1
            except Exception as e:
                logger.exception(f"Failed to launch Celery task for Job {job.id}. Error: {e}")
                # В реальной системе здесь можно было бы обновить статус Job на FAILED.

        if jobs_launched == 0 and len(channel_inputs) > 0:
            run.status = "FAILED"
            logger.error(f"Run {run.id} failed to launch any jobs.")
        elif jobs_launched < len(channel_inputs):
             run.status = "PARTIALLY_PROCESSING"
             logger.warning(f"Run {run.id} launched only {jobs_launched}/{len(channel_inputs)} jobs.")
        else:
            run.status = "PROCESSING"

        return {
            "run_id": run.id,
            "jobs_created": jobs_launched,
            "status": run.status,
            "run_details": run.model_dump()
        }
