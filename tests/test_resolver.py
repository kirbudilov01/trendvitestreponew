import pytest
from unittest.mock import MagicMock

from collector.resolver import resolve_youtube_channel, ResolveStatus
from collector.yt.client import YouTubeClient

@pytest.fixture
def mock_youtube_client() -> MagicMock:
    """Provides a MagicMock instance of YouTubeClient."""
    client = MagicMock(spec=YouTubeClient)
    # Mock the universal method
    client.channels_list = MagicMock()
    return client

# 1. Tests for Direct Channel ID (no API call)
@pytest.mark.parametrize("input_str, expected_id", [
    ("https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw", "UC-lHJZR3Gqxm24_Vd_AJ5Yw"),
    ("UC-lHJZR3Gqxm24_Vd_AJ5Yw", "UC-lHJZR3Gqxm24_Vd_AJ5Yw")
])
def test_resolve_direct_channel_id(input_str, expected_id, mock_youtube_client):
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == expected_id
    mock_youtube_client.channels_list.assert_not_called()

# 2. Tests for /user/ URLs
def test_resolve_user_url_success(mock_youtube_client):
    mock_youtube_client.channels_list.return_value = {"items": [{"id": "UC_user_success_id"}]}
    result = resolve_youtube_channel("https://www.youtube.com/user/MrBeast6000", mock_youtube_client)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == "UC_user_success_id"
    mock_youtube_client.channels_list.assert_called_once_with(part="id", forUsername="MrBeast6000")

def test_resolve_user_url_failure(mock_youtube_client):
    mock_youtube_client.channels_list.return_value = None # Simulate client returning None
    result = resolve_youtube_channel("https://www.youtube.com/user/nonexistent", mock_youtube_client)
    assert result.status == ResolveStatus.FAILED
    mock_youtube_client.channels_list.assert_called_once_with(part="id", forUsername="nonexistent")

# 3. Tests for Handle URLs and Raw Handles
@pytest.mark.parametrize("input_str, expected_handle", [
    ("https://www.youtube.com/@MrBeast", "MrBeast"),
    ("@MrBeast", "MrBeast"),
    ("MrBeast", "MrBeast")
])
def test_resolve_handle_success(input_str, expected_handle, mock_youtube_client):
    mock_youtube_client.channels_list.return_value = {"items": [{"id": "UC_handle_success_id"}]}
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == "UC_handle_success_id"
    mock_youtube_client.channels_list.assert_called_once_with(part="id", forHandle=expected_handle)

@pytest.mark.parametrize("input_str, expected_handle", [
    ("https://www.youtube.com/@nonexistent", "nonexistent"),
    ("@nonexistent", "nonexistent")
])
def test_resolve_handle_failure(input_str, expected_handle, mock_youtube_client):
    mock_youtube_client.channels_list.return_value = {"items": []} # Simulate empty response
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.FAILED
    mock_youtube_client.channels_list.assert_called_once_with(part="id", forHandle=expected_handle)

# 4. Tests for types that NEED search fallback
def test_custom_url_needs_search_fallback(mock_youtube_client):
    input_str = "https://www.youtube.com/c/customurl"
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.NEEDS_SEARCH_FALLBACK
    mock_youtube_client.channels_list.assert_not_called()

# 5. Test for unrecognized inputs
def test_unrecognized_input_fails(mock_youtube_client):
    input_str = "this is just a random sentence"
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.FAILED
    mock_youtube_client.channels_list.assert_not_called()
