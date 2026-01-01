import pytest
from unittest.mock import AsyncMock

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

    # Patch the factory function
    monkeypatch.setattr("collector.limiter.get_redis_client", lambda: mock_redis)
    monkeypatch.setattr("collector.redis_client.get_redis_client", lambda: mock_redis)

    return mock_redis
