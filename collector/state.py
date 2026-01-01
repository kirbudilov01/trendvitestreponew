from threading import Lock
from typing import Dict, List, Optional

from .models import Run, Job

class InMemoryState:
    """
    A thread-safe in-memory storage for Runs and Jobs.
    This is a simple implementation for demonstration purposes.
    In a production environment, this would be replaced by a persistent database.
    """
    def __init__(self):
        self._runs: Dict[int, Run] = {}
        self._jobs: Dict[int, Job] = {}
        self._jobs_by_run: Dict[int, List[int]] = {}
        self._lock = Lock()
        self._run_id_counter = 0
        self._job_id_counter = 0

    def get_next_run_id(self) -> int:
        with self._lock:
            self._run_id_counter += 1
            return self._run_id_counter

    def get_next_job_id(self) -> int:
        with self._lock:
            self._job_id_counter += 1
            return self._job_id_counter

    def create_run(self, run: Run):
        with self._lock:
            self._runs[run.id] = run
            self._jobs_by_run[run.id] = []

    def get_run(self, run_id: int) -> Optional[Run]:
        with self._lock:
            return self._runs.get(run_id)

    def update_run(self, run: Run):
        with self._lock:
            if run.id in self._runs:
                self._runs[run.id] = run

    def create_job(self, job: Job):
        with self._lock:
            self._jobs[job.id] = job
            if job.run_id in self._jobs_by_run:
                self._jobs_by_run[job.run_id].append(job.id)

    def get_job(self, job_id: int) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job: Job):
        with self._lock:
            if job.id in self._jobs:
                self._jobs[job.id] = job

    def get_jobs_for_run(self, run_id: int) -> List[Job]:
        with self._lock:
            job_ids = self._jobs_by_run.get(run_id, [])
            return [self._jobs[job_id] for job_id in job_ids if job_id in self._jobs]

    def clear_all(self):
        with self._lock:
            self._runs.clear()
            self._jobs.clear()
            self._jobs_by_run.clear()
            self._run_id_counter = 0
            self._job_id_counter = 0

# Singleton instance
STATE = InMemoryState()
