import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture(autouse=True)
def mock_redis_client(monkeypatch):
    """
    Mock the redis client to avoid actual network calls and connection errors.
    """
    mock_redis = AsyncMock()
    mock_redis.zremrangebyscore = AsyncMock(return_value=None)
    mock_redis.zcard = AsyncMock(return_value=0)
    mock_redis.zadd = AsyncMock(return_value=None)
    mock_redis.zrange = AsyncMock(return_value=[])
    mock_redis.aclose = AsyncMock(return_value=None)

    # Configure redis.pipeline() to be an async context manager
    pipeline_mock = AsyncMock()
    pipeline_mock.__aenter__.return_value = pipeline_mock
    pipeline_mock.__aexit__.return_value = None
    # The pipeline's execute should be awaitable
    pipeline_mock.execute = AsyncMock(return_value=[None, 0])
    mock_redis.pipeline = MagicMock(return_value=pipeline_mock)

    # Since limiter now directly imports the client, we patch the client itself.
    monkeypatch.setattr("collector.limiter.shared_redis_client", mock_redis)
    monkeypatch.setattr("collector.redis_client.shared_redis_client", mock_redis)

    return mock_redis
