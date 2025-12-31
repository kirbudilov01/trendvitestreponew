import pytest
from unittest.mock import patch, call
from freezegun import freeze_time
from celery.exceptions import SoftTimeLimitExceeded

from collector.orchestrator import Orchestrator
from collector.state import STATE
from collector.models import Run, Job
# Импортируем саму задачу для прямого вызова в TTL тесте
from collector.tasks import process_channel_job

# -- Fixture to ensure clean state for each test --

@pytest.fixture(autouse=True)
def clear_state_before_each_test():
    """Автоматически очищает InMemoryState перед каждым тестом."""
    STATE.clear_all()
    yield

# -- Tests for Orchestrator --

@patch('collector.orchestrator.process_channel_job.delay')
def test_start_run_deduplicates_inputs(mock_celery_delay):
    orchestrator = Orchestrator()
    inputs = ["@handle1", "UC123", "  @handle1  ", "UC123"]

    result = orchestrator.start_run(analysis_id=1, owner_id=1, channel_inputs=inputs)

    assert result["jobs_created"] == 2 # Должно быть 2 уникальных инпута
    mock_celery_delay.assert_has_calls([
        call(job_id=1, run_id=result["run_id"]),
        call(job_id=2, run_id=result["run_id"])
    ], any_order=True)

def test_get_run_status_calculates_progress():
    run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
    STATE.create_run(run)
    STATE.create_job(Job(id=1, run_id=1, input_channel="c1", status="DONE"))
    STATE.create_job(Job(id=2, run_id=1, input_channel="c2", status="FAILED"))

    orchestrator = Orchestrator()
    status = orchestrator.get_run_status(1)

    assert status["progress"] == 1.0
    assert status["summary"] is None # Summary еще не должен быть

def test_get_run_status_calculates_partial_progress():
    run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
    STATE.create_run(run)
    STATE.create_job(Job(id=1, run_id=1, input_channel="c1", status="DONE"))
    STATE.create_job(Job(id=2, run_id=1, input_channel="c2", status="PENDING"))

    orchestrator = Orchestrator()
    status = orchestrator.get_run_status(1)

    assert status["progress"] == 0.5

@freeze_time("2024-01-01 12:00:00")
def test_finalize_run_sets_summary_and_finished_at():
    orchestrator = Orchestrator()

    with freeze_time("2024-01-01 11:59:50"):
        run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
        STATE.create_run(run)

    STATE.create_job(Job(id=1, run_id=1, input_channel="c1", status="DONE"))
    STATE.create_job(Job(id=2, run_id=1, input_channel="c2", status="FAILED"))

    orchestrator.finalize_run(1)

    updated_run = STATE.get_run(1)
    assert updated_run.status == "FINISHED"
    assert updated_run.finished_at is not None
    assert updated_run.summary is not None
    assert updated_run.summary["total"] == 2
    assert updated_run.summary["done"] == 1
    assert updated_run.summary["failed"] == 1
    assert updated_run.summary["duration_seconds"] == 10.0

# -- Test for TTL Logic in Celery Task --

@patch('collector.tasks.YouTubeClient') # Мокаем весь клиент, чтобы избежать проблем с ключами
@patch('collector.tasks.resolve_youtube_channel', side_effect=SoftTimeLimitExceeded)
@patch('collector.tasks.finalize_run_task.delay')
@patch('celery.app.task.Task.update_state') # Мокаем update_state
def test_process_channel_job_handles_ttl_exceeded(mock_update_state, mock_finalize_delay, mock_resolver, mock_yt_client):
    # 1. Setup state
    run = Run(id=1, analysis_id=1, owner_id=1, status="RUNNING")
    STATE.create_run(run)
    job = Job(id=1, run_id=1, input_channel="test_channel")
    STATE.create_job(job)

    # 2. Прямой вызов задачи.
    #    Celery @task декоратор добавляет .__wrapped__ для доступа к оригинальной функции.
    #    Первый аргумент 'self' передается автоматически благодаря 'bind=True'.
    process_channel_job.__wrapped__(job_id=1, run_id=1)

    # 3. Проверяем состояние Job
    updated_job = STATE.get_job(1)
    assert updated_job.status == "FAILED"
    assert updated_job.last_error == "TTL exceeded"

    # 4. Проверяем, что finalizer все равно был вызван
    mock_finalize_delay.assert_called_once_with(1)
