import pytest
from unittest.mock import AsyncMock, patch

from collector.resolver import resolve_youtube_channel, ResolveStatus

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_yt_client():
    client = AsyncMock()
    client.get_channel_by_handle = AsyncMock()
    return client

async def test_resolve_direct_channel_id():
    result = await resolve_youtube_channel("https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw", 1)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == "UC-lHJZR3Gqxm24_Vd_AJ5Yw"

async def test_resolve_valid_handle(mock_yt_client):
    mock_yt_client.get_channel_by_handle.return_value = {"items": [{"id": "UCX6OQ3DkcsbYNE6H8uQQuVA"}]}

    # We need to patch the global client instance used by the resolver
    with patch('collector.resolver.youtube_client', mock_yt_client):
        result = await resolve_youtube_channel("https://www.youtube.com/@MrBeast", 1)
        assert result.status == ResolveStatus.RESOLVED
        assert result.youtube_channel_id == "UCX6OQ3DkcsbYNE6H8uQQuVA"
        mock_yt_client.get_channel_by_handle.assert_called_once_with(1, "@MrBeast")

async def test_resolve_invalid_handle(mock_yt_client):
    mock_yt_client.get_channel_by_handle.return_value = {"items": []}

    with patch('collector.resolver.youtube_client', mock_yt_client):
        result = await resolve_youtube_channel("@nonexistent", 1)
        assert result.status == ResolveStatus.FAILED
        assert "not found" in result.error
