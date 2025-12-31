import logging
from typing import List, Dict, Any, Optional
import itertools
from datetime import datetime, timezone

from .models import Run, Job
from .state import STATE
from .tasks import process_channel_job

logger = logging.getLogger(__name__)

# Генераторы ID остаются для простоты, но теперь они будут использоваться
# для создания объектов перед их сохранением в STATE.
_job_id_counter = itertools.count(start=1)
_run_id_counter = itertools.count(start=1)


class Orchestrator:
    """
    Управляет жизненным циклом 'Run': создание, отслеживание прогресса и финализация.
    """
    def start_run(self, analysis_id: int, owner_id: int, channel_inputs: List[str]) -> Dict[str, Any]:
        run_id = next(_run_id_counter)
        run = Run(id=run_id, analysis_id=analysis_id, owner_id=owner_id, status="RUNNING")
        STATE.create_run(run)
        logger.info(f"Started Run {run.id} for analysis {analysis_id}.")

        jobs_launched = 0
        for channel_input in channel_inputs:
            if not channel_input or not channel_input.strip():
                continue

            job_id = next(_job_id_counter)
            job = Job(id=job_id, run_id=run.id, input_channel=channel_input, status="PENDING")
            STATE.create_job(job)

            process_channel_job.delay(job_id=job.id, run_id=run.id)
            jobs_launched += 1

        return {"run_id": run.id, "jobs_created": jobs_launched}

    def get_run_status(self, run_id: int) -> Optional[Dict[str, Any]]:
        run = STATE.get_run(run_id)
        if not run:
            return None

        jobs = STATE.get_jobs_for_run(run_id)
        total_jobs = len(jobs)

        status_counts = {"PENDING": 0, "PROCESSING": 0, "DONE": 0, "FAILED": 0}
        failed_jobs_details = []

        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
            if job.status == "FAILED":
                failed_jobs_details.append({
                    "job_id": job.id,
                    "input": job.input_channel,
                    "error": job.last_error
                })

        done_count = status_counts.get("DONE", 0)
        failed_count = status_counts.get("FAILED", 0)
        progress = (done_count + failed_count) / total_jobs if total_jobs > 0 else 0

        return {
            "run_id": run.id,
            "run_status": run.status,
            "progress": f"{progress:.0%}",
            "total_jobs": total_jobs,
            "status_counts": status_counts,
            "failed_jobs": failed_jobs_details
        }

    def finalize_run(self, run_id: int) -> bool:
        run = STATE.get_run(run_id)
        if not run or run.status == "FINISHED":
            return False

        jobs = STATE.get_jobs_for_run(run_id)
        total_jobs = len(jobs)
        finished_jobs = [j for j in jobs if j.status in ["DONE", "FAILED"]]

        if len(finished_jobs) == total_jobs and total_jobs > 0:
            run.status = "FINISHED"
            run.updated_at = datetime.now(timezone.utc)

            done_count = len([j for j in jobs if j.status == "DONE"])
            failed_count = total_jobs - done_count
            duration = (run.updated_at - run.created_at).total_seconds()

            summary = {
                "total": total_jobs,
                "done": done_count,
                "failed": failed_count,
                "duration_seconds": round(duration, 2)
            }
            # В реальной системе это было бы сохранено в Run
            logger.info(f"Run {run_id} finalized. Summary: {summary}")
            # Концептуально, можно добавить summary в модель Run
            return True

        return False
