import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from googleapiclient.errors import HttpError
from collector.yt_client import YouTubeClientRotator

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


class MockHttpResponse:
    def __init__(self, status_code, reason=""):
        self.status = status_code
        self.reason = reason

@pytest.fixture
def mock_build():
    with patch("collector.yt_client.build_youtube_client") as mock:
        yield mock

async def test_get_key_rotation():
    """ Test that keys are rotated correctly on successful calls. """
    client = YouTubeClientRotator(api_keys=["key1", "key2", "key3"])
    
    first_key = await client._get_key()
    assert first_key == "key1"
    
    second_key = await client._get_key()
    assert second_key == "key2"

    third_key = await client._get_key()
    assert third_key == "key3"

    fourth_key = await client._get_key()
    assert fourth_key == "key1" # Rotated back to the start

async def test_cooldown_on_quota_error(mock_build):
    """ Test that a key is put on cooldown when a quota error occurs. """
    # Mock HttpError content
    error_content = b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
    http_error = HttpError(MockHttpResponse(403), error_content)

    # Configure the mock to raise the error
    # We need to mock the async behavior correctly
    async_mock_execute = AsyncMock(side_effect=http_error)
    mock_channels_list = MagicMock()
    mock_channels_list.execute = async_mock_execute
    mock_channels = MagicMock()
    mock_channels.list.return_value = mock_channels_list
    mock_youtube_service = MagicMock()
    mock_youtube_service.channels.return_value = mock_channels

    # We patch `asyncio.to_thread` to avoid actual thread creation in tests
    with patch("asyncio.to_thread", side_effect=http_error) as mock_to_thread:
        mock_build.return_value = mock_youtube_service
        
        client = YouTubeClientRotator(api_keys=["key1", "key2"], cooldown_time=0.1)
        
        # The first call should fail and put key1 on cooldown
        with pytest.raises(RuntimeError, match="No available API keys"):
            # This will loop until it runs out of keys
            await client.safe_execute(
                owner_id="test_owner",
                func=lambda youtube, **kwargs: youtube.channels().list(**kwargs).execute(),
                part="snippet",
                id="some_id"
            )

    # Check that key1 is in cooldown
    assert "key1" in client._cooldown_keys
    # key2 should also be on cooldown as it would have been tried and failed
    assert "key2" in client._cooldown_keys

    # Wait for cooldown to expire
    await asyncio.sleep(0.2)

    # After cooldown, key1 should be available again
    key = await client._get_key()
    assert key == "key1" or key == "key2"


async def test_reraise_on_non_quota_error(mock_build):
    """ Test that non-quota HttpErrors are re-raised. """
    error_content = b'{"error": {"errors": [{"reason": "invalid_id"}]}}'
    http_error = HttpError(MockHttpResponse(400), error_content)

    with patch("asyncio.to_thread", side_effect=http_error):
        client = YouTubeClientRotator(api_keys=["key1"])

        with pytest.raises(HttpError) as excinfo:
            await client.safe_execute(
                owner_id="test_owner",
                func=lambda youtube, **kwargs: youtube.channels().list(**kwargs).execute(),
                part="snippet",
                id="invalid"
            )
    
    assert "invalid_id" in str(excinfo.value.content)

async def test_no_available_keys_error():
    """ Test that a RuntimeError is raised if all keys are on cooldown. """
    client = YouTubeClientRotator(api_keys=["key1"], cooldown_time=10)
    await client._cooldown_key("key1")
    
    with pytest.raises(RuntimeError, match="No available API keys"):
        await client._get_key()
