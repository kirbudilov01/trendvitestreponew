import pytest
from unittest.mock import AsyncMock, ANY

from collector.resolver_v2 import resolve_youtube_channel_id
from collector.models import ResolveResult

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_yt_client():
    client = AsyncMock()
    client.safe_execute = AsyncMock()
    return client

async def test_resolve_direct_channel_id(mock_yt_client):
    """ Test that a direct UC... channel ID is resolved without an API call. """
    input_str = "https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw"
    result = await resolve_youtube_channel_id(input_str, owner_id=1, youtube_client=mock_yt_client)

    assert result.youtube_channel_id == "UC-lHJZR3Gqxm24_Vd_AJ5Yw"
    assert result.error is None
    assert result.needs_search_fallback is False
    mock_yt_client.safe_execute.assert_not_called()

async def test_resolve_valid_handle(mock_yt_client):
    """ Test that a valid @handle is resolved via an API call. """
    input_str = "https://www.youtube.com/@MrBeast"
    owner_id = 1

    # Mock the API response
    api_response = {
        "items": [{"id": "UCX6OQ3DkcsbYNE6H8uQQuVA"}]
    }
    mock_yt_client.safe_execute.return_value = api_response

    result = await resolve_youtube_channel_id(input_str, owner_id=owner_id, youtube_client=mock_yt_client)

    assert result.youtube_channel_id == "UCX6OQ3DkcsbYNE6H8uQQuVA"
    assert result.username == "@MrBeast"
    assert result.error is None

    mock_yt_client.safe_execute.assert_called_once_with(
        owner_id=owner_id,
        func=ANY,
        forHandle="MrBeast", # Note: no '@'
        part="id",
        maxResults=1,
    )

async def test_resolve_invalid_handle(mock_yt_client):
    """ Test that an invalid @handle returns an error. """
    input_str = "https://www.youtube.com/@nonexistenthandle12345"
    owner_id = 1

    # Mock an empty API response
    api_response = {"items": []}
    mock_yt_client.safe_execute.return_value = api_response

    result = await resolve_youtube_channel_id(input_str, owner_id=owner_id, youtube_client=mock_yt_client)

    assert result.youtube_channel_id is None
    assert "not found" in result.error
    assert result.needs_search_fallback is False # It's a definitive failure

    mock_yt_client.safe_execute.assert_called_once()

async def test_needs_search_fallback(mock_yt_client):
    """ Test that an unresolvable input is marked for search fallback. """
    input_str = "PewDiePie" # A string that doesn't match ID or handle patterns
    result = await resolve_youtube_channel_id(input_str, owner_id=1, youtube_client=mock_yt_client)

    assert result.youtube_channel_id is None
    assert result.error is None
    assert result.needs_search_fallback is True
    mock_yt_client.safe_execute.assert_not_called()

async def test_resolve_c_url_needs_fallback(mock_yt_client):
    """ Test that a /c/ URL is marked for search fallback. """
    input_str = "https://www.youtube.com/c/PewDiePie"
    result = await resolve_youtube_channel_id(input_str, owner_id=1, youtube_client=mock_yt_client)

    assert result.youtube_channel_id is None
    assert result.needs_search_fallback is True
    assert result.username == "PewDiePie"
    mock_yt_client.safe_execute.assert_not_called()

async def test_resolve_user_url_needs_fallback(mock_yt_client):
    """ Test that a /user/ URL is marked for search fallback. """
    input_str = "https://www.youtube.com/user/MrBeast6000"
    result = await resolve_youtube_channel_id(input_str, owner_id=1, youtube_client=mock_yt_client)

    assert result.youtube_channel_id is None
    assert result.needs_search_fallback is True
    assert result.username == "MrBeast6000"
    mock_yt_client.safe_execute.assert_not_called()
