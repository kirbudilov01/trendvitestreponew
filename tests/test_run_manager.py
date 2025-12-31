import pytest
from unittest.mock import patch, call

from collector.run_manager import RunManager

# Используем patch, чтобы заменить .delay метод нашей Celery-задачи на мок
@patch('collector.run_manager.process_channel_job.delay')
def test_start_analysis_launches_jobs_for_each_input(mock_celery_delay):
    """
    Проверяет, что RunManager.start_analysis вызывает Celery-задачу для каждого
    валидного входного канала с правильными аргументами.
    """
    manager = RunManager()
    channel_inputs = [
        "https://www.youtube.com/user/testuser1",
        "@testhandle",
        " ",  # Невалидный инпут для проверки
        "UC-lHJZR3Gqxm24_Vd_AJ5Yw"
    ]

    result = manager.start_analysis(
        analysis_id=101,
        owner_id=202,
        channel_inputs=channel_inputs
    )

    # 1. Проверяем, что результат содержит корректные данные
    assert result["run_id"] is not None
    assert result["jobs_created"] == 3 # Один инпут был пустым
    assert result["status"] == "PARTIALLY_PROCESSING"

    # 2. Проверяем, что .delay был вызван правильное количество раз
    assert mock_celery_delay.call_count == 3

    # 3. Проверяем, что .delay был вызван с правильными аргументами
    # Job ID генерируются авто-инкрементом, поэтому мы ожидаем 1, 2, 3
    expected_calls = [
        call(job_id=1, input_channel_str="https://www.youtube.com/user/testuser1"),
        call(job_id=2, input_channel_str="@testhandle"),
        call(job_id=3, input_channel_str="UC-lHJZR3Gqxm24_Vd_AJ5Yw")
    ]
    mock_celery_delay.assert_has_calls(expected_calls, any_order=False)

@patch('collector.run_manager.process_channel_job.delay')
def test_start_analysis_handles_no_inputs(mock_celery_delay):
    """
    Проверяет, что RunManager корректно обрабатывает случай с пустым списком каналов.
    """
    manager = RunManager()
    result = manager.start_analysis(analysis_id=102, owner_id=203, channel_inputs=[])

    assert result["run_id"] is None
    assert result["jobs_created"] == 0
    mock_celery_delay.assert_not_called()

@patch('collector.run_manager.process_channel_job.delay')
def test_start_analysis_handles_only_empty_inputs(mock_celery_delay):
    """
    Проверяет, что RunManager не запускает задачи, если все инпуты пустые или состоят из пробелов.
    """
    manager = RunManager()
    result = manager.start_analysis(analysis_id=103, owner_id=204, channel_inputs=["  ", "", " "])

    assert result["run_id"] is not None # Run создается, но помечается как FAILED
    assert result["jobs_created"] == 0
    assert result["status"] == "FAILED"
    mock_celery_delay.assert_not_called()
