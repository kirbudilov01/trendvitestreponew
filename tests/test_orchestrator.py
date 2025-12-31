import pytest
from unittest.mock import patch, call
from freezegun import freeze_time

from collector.orchestrator import Orchestrator
from collector.state import STATE
from collector.models import Run, Job

# -- Fixture to ensure clean state for each test --

@pytest.fixture(autouse=True)
def clear_state_before_each_test():
    """Автоматически очищает InMemoryState перед каждым тестом."""
    STATE.clear_all()
    yield

# -- Tests for Orchestrator --

@patch('collector.orchestrator.process_channel_job.delay')
def test_start_run_creates_run_and_jobs_in_state(mock_celery_delay):
    orchestrator = Orchestrator()
    inputs = ["@handle1", "UC123"]

    result = orchestrator.start_run(analysis_id=1, owner_id=1, channel_inputs=inputs)
    run_id = result["run_id"]

    # Проверяем Run
    run = STATE.get_run(run_id)
    assert run is not None
    assert run.status == "RUNNING"
    assert run.analysis_id == 1

    # Проверяем Jobs
    jobs = STATE.get_jobs_for_run(run_id)
    assert len(jobs) == 2
    assert jobs[0].status == "PENDING"
    assert jobs[0].input_channel == "@handle1"
    assert jobs[1].status == "PENDING"

    # Проверяем вызовы Celery
    mock_celery_delay.assert_has_calls([
        call(job_id=jobs[0].id, run_id=run_id),
        call(job_id=jobs[1].id, run_id=run_id)
    ])

def test_get_run_status_calculates_progress():
    # 1. Setup state manually
    run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
    STATE.create_run(run)
    STATE.create_job(Job(id=1, run_id=1, input_channel="c1", status="DONE"))
    STATE.create_job(Job(id=2, run_id=1, input_channel="c2", status="FAILED", last_error="Test Error"))
    STATE.create_job(Job(id=3, run_id=1, input_channel="c3", status="PROCESSING"))
    STATE.create_job(Job(id=4, run_id=1, input_channel="c4", status="PENDING"))

    # 2. Call get_run_status
    orchestrator = Orchestrator()
    status = orchestrator.get_run_status(1)

    # 3. Assert results
    assert status["run_id"] == 1
    assert status["progress"] == "50%" # (DONE + FAILED) / TOTAL
    assert status["total_jobs"] == 4
    assert status["status_counts"] == {"PENDING": 1, "PROCESSING": 1, "DONE": 1, "FAILED": 1}
    assert len(status["failed_jobs"]) == 1
    assert status["failed_jobs"][0]["error"] == "Test Error"

@freeze_time("2024-01-01 12:00:00")
def test_finalize_run_when_all_jobs_are_finished():
    orchestrator = Orchestrator()

    # Setup: создаем Run, который начался 10 секунд назад
    with freeze_time("2024-01-01 11:59:50"):
        run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
        STATE.create_run(run)

    STATE.create_job(Job(id=1, run_id=1, input_channel="c1", status="DONE"))
    STATE.create_job(Job(id=2, run_id=1, input_channel="c2", status="FAILED"))

    finalized = orchestrator.finalize_run(1)

    assert finalized is True
    updated_run = STATE.get_run(1)
    assert updated_run.status == "FINISHED"
    assert updated_run.updated_at.isoformat() == "2024-01-01T12:00:00+00:00"
    # Здесь можно было бы проверить и записанную статистику, если бы она сохранялась в модель

def test_finalize_run_does_not_finalize_if_jobs_are_pending():
    orchestrator = Orchestrator()
    run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
    STATE.create_run(run)
    STATE.create_job(Job(id=1, run_id=1, input_channel="c1", status="DONE"))
    STATE.create_job(Job(id=2, run_id=1, input_channel="c2", status="PENDING")) # Один не завершен

    finalized = orchestrator.finalize_run(1)

    assert finalized is False
    updated_run = STATE.get_run(1)
    assert updated_run.status == "RUNNING" # Статус не должен измениться
