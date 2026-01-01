import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .models import Run, Job
from .state import STATE
from .tasks import process_channel_job

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Управляет жизненным циклом 'Run': создание, отслеживание прогресса и финализация.
    """
    def start_run(self, analysis_id: int, owner_id: int, channel_inputs: List[str]) -> Dict[str, Any]:
        run_id = STATE.get_next_run_id()
        run = Run(id=run_id, analysis_id=analysis_id, owner_id=owner_id, status="RUNNING")
        STATE.create_run(run)
        logger.info(f"Started Run {run.id} for analysis {analysis_id}.")

        # Дедупликация инпутов
        unique_inputs = sorted(list(set(inp.strip() for inp in channel_inputs if inp and inp.strip())))

        jobs_launched = 0
        for channel_input in unique_inputs:
            job_id = STATE.get_next_job_id()
            job = Job(id=job_id, run_id=run.id, input_channel=channel_input, status="PENDING")
            STATE.create_job(job)

            process_channel_job.delay(job_id=job.id, run_id=run.id)
            jobs_launched += 1

        # Если после дедупликации не осталось каналов для обработки
        if jobs_launched == 0:
            self.finalize_run(run.id)

        return {"run_id": run.id, "jobs_created": jobs_launched}

    def get_run_status(self, run_id: int) -> Optional[Dict[str, Any]]:
        run = STATE.get_run(run_id)
        if not run:
            return None

        jobs = STATE.get_jobs_for_run(run_id)
        total_jobs = len(jobs)

        status_counts = {"PENDING": 0, "PROCESSING": 0, "DONE": 0, "FAILED": 0, "NEEDS_SEARCH": 0}
        failed_jobs_details = []

        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
            if job.status == "FAILED":
                failed_jobs_details.append({
                    "job_id": job.id,
                    "input": job.input_channel,
                    "error": job.last_error
                })

        finished_count = sum(status_counts.get(s, 0) for s in ["DONE", "FAILED", "NEEDS_SEARCH"])
        progress = finished_count / total_jobs if total_jobs > 0 else 1.0

        return {
            "run_id": run.id,
            "run_status": run.status,
            "progress": progress,
            "total_jobs": total_jobs,
            "status_counts": status_counts,
            "failed_jobs": failed_jobs_details,
            "summary": run.summary
        }

    def finalize_run(self, run_id: int) -> bool:
        run = STATE.get_run(run_id)
        if not run or run.status == "FINISHED":
            return False

        jobs = STATE.get_jobs_for_run(run_id)
        total_jobs = len(jobs)

        # Условие финализации: нет задач в PENDING или PROCESSING
        pending_or_processing = [j for j in jobs if j.status in ["PENDING", "PROCESSING"]]
        if len(pending_or_processing) > 0:
            return False

        run.status = "FINISHED"
        run.finished_at = datetime.now(timezone.utc)

        status_counts = self.get_run_status(run_id)["status_counts"]
        duration = (run.finished_at - run.created_at).total_seconds()

        run.summary = {
            "total": total_jobs,
            "done": status_counts.get("DONE", 0),
            "failed": status_counts.get("FAILED", 0),
            "needs_search": status_counts.get("NEEDS_SEARCH", 0),
            "duration_seconds": round(duration, 2)
        }

        logger.info(f"Run {run_id} finalized. Summary: {run.summary}")
        return True
