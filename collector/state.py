import logging
from typing import Dict, List, Optional
from threading import Lock

from .models import Run, Job

logger = logging.getLogger(__name__)

class InMemoryState:
    """
    Простое потокобезопасное in-memory хранилище для симуляции базы данных.
    Использует блокировки для предотвращения гонок данных при одновременном
    доступе из разных Celery-воркеров (концептуально).
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        # Реализуем Singleton-паттерн, чтобы все части приложения
        # работали с одним и тем же состоянием.
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InMemoryState, cls).__new__(cls)
                cls._instance._runs: Dict[int, Run] = {}
                cls._instance._jobs: Dict[int, Job] = {}
                logger.info("InMemoryState initialized.")
        return cls._instance

    def create_run(self, run: Run) -> None:
        with self._lock:
            if run.id in self._runs:
                raise ValueError(f"Run with id {run.id} already exists.")
            self._runs[run.id] = run
            logger.debug(f"Run {run.id} created in state.")

    def get_run(self, run_id: int) -> Optional[Run]:
        with self._lock:
            return self._runs.get(run_id)

    def create_job(self, job: Job) -> None:
        with self._lock:
            if job.id in self._jobs:
                raise ValueError(f"Job with id {job.id} already exists.")
            self._jobs[job.id] = job
            logger.debug(f"Job {job.id} created in state.")

    def get_job(self, job_id: int) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job: Job) -> None:
        with self._lock:
            if job.id not in self._jobs:
                raise ValueError(f"Job with id {job.id} not found for update.")
            self._jobs[job.id] = job
            logger.debug(f"Job {job.id} updated in state.")

    def get_jobs_for_run(self, run_id: int) -> List[Job]:
        with self._lock:
            return [job for job in self._jobs.values() if job.run_id == run_id]

    def clear_all(self) -> None:
        """Вспомогательный метод для очистки состояния (полезен в тестах)."""
        with self._lock:
            self._runs.clear()
            self._jobs.clear()
            logger.warning("InMemoryState cleared.")

# Глобальный экземпляр, который будет использоваться во всем приложении
STATE = InMemoryState()
