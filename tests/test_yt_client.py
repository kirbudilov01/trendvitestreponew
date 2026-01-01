import asyncio
import pytest
from unittest.mock import patch, MagicMock
from googleapiclient.errors import HttpError

from collector.yt.client import YouTubeClient

pytestmark = pytest.mark.asyncio

class MockHttpResponse:
    def __init__(self, status, reason=""):
        self.status = status
        self.reason = reason

async def test_key_rotation_on_quota_error():
    client = YouTubeClient(api_keys=["key1", "key2"], cooldown_time=0.1)

    error_content = b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
    http_error = HttpError(MockHttpResponse(403), error_content)

    func = MagicMock(side_effect=http_error)

    with patch('asyncio.to_thread', side_effect=http_error):
        # First call fails with key1, exhausting retries
        with pytest.raises(HttpError):
            await client._safe_execute("owner", func, max_retries=1)
        assert "key1" in client._cooldown_keys
        assert "key2" not in client._cooldown_keys

        # Second call fails with key2, exhausting retries
        with pytest.raises(HttpError):
            await client._safe_execute("owner", func, max_retries=1)
        assert "key2" in client._cooldown_keys

        # Now all keys are on cooldown
        with pytest.raises(RuntimeError, match="No available API keys"):
            await client._get_key()

        # Wait for cooldown to expire
        await asyncio.sleep(0.2)

        # Keys should be available again
        key = await client._get_key()
        assert key in ["key1", "key2"]
