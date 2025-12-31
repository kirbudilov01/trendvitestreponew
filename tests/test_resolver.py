import pytest
from unittest.mock import MagicMock

from collector.resolver import resolve_youtube_channel, ResolveStatus
from collector.youtube_client import YouTubeClient

@pytest.fixture
def mock_youtube_client() -> MagicMock:
    """Provides a MagicMock instance of YouTubeClient."""
    # We mock both methods on the client
    client = MagicMock(spec=YouTubeClient)
    client.get_channel_id_for_user = MagicMock()
    client.get_channel_id_for_handle = MagicMock()
    return client

# 1. Tests for Direct Channel ID (no API call)
@pytest.mark.parametrize("input_str, expected_id", [
    ("https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw", "UC-lHJZR3Gqxm24_Vd_AJ5Yw"),
    ("Some text with UC-lHJZR3Gqxm24_Vd_AJ5Yw inside.", "UC-lHJZR3Gqxm24_Vd_AJ5Yw"),
    ("UC-lHJZR3Gqxm24_Vd_AJ5Yw", "UC-lHJZR3Gqxm24_Vd_AJ5Yw")
])
def test_resolve_direct_channel_id(input_str, expected_id, mock_youtube_client):
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == expected_id
    assert result.input_type == "CHANNEL_ID"
    mock_youtube_client.get_channel_id_for_user.assert_not_called()
    mock_youtube_client.get_channel_id_for_handle.assert_not_called()

# 2. Tests for /user/ URLs
def test_resolve_user_url_success(mock_youtube_client):
    mock_youtube_client.get_channel_id_for_user.return_value = "UC_user_success_id"
    result = resolve_youtube_channel("https://www.youtube.com/user/MrBeast6000", mock_youtube_client)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == "UC_user_success_id"
    assert result.input_type == "USER_URL"
    mock_youtube_client.get_channel_id_for_user.assert_called_once_with("MrBeast6000")
    mock_youtube_client.get_channel_id_for_handle.assert_not_called()

def test_resolve_user_url_failure(mock_youtube_client):
    mock_youtube_client.get_channel_id_for_user.return_value = None
    result = resolve_youtube_channel("https://www.youtube.com/user/nonexistent", mock_youtube_client)
    assert result.status == ResolveStatus.FAILED
    assert result.youtube_channel_id is None
    assert result.input_type == "USER_URL"
    mock_youtube_client.get_channel_id_for_user.assert_called_once_with("nonexistent")
    mock_youtube_client.get_channel_id_for_handle.assert_not_called()

# 3. Tests for Handle URLs (/@...) and Raw Handles
@pytest.mark.parametrize("input_str, expected_handle_arg", [
    ("https://www.youtube.com/@MrBeast", "@MrBeast"),
    ("@MrBeast", "@MrBeast"),
    ("MrBeast", "MrBeast")
])
def test_resolve_handle_success(input_str, expected_handle_arg, mock_youtube_client):
    mock_youtube_client.get_channel_id_for_handle.return_value = "UC_handle_success_id"
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.RESOLVED
    assert result.youtube_channel_id == "UC_handle_success_id"
    # The input type depends on whether it was a URL or raw handle
    assert result.input_type in ["HANDLE", "RAW_HANDLE"]
    mock_youtube_client.get_channel_id_for_handle.assert_called_once_with(expected_handle_arg)
    mock_youtube_client.get_channel_id_for_user.assert_not_called()

@pytest.mark.parametrize("input_str, expected_handle_arg", [
    ("https://www.youtube.com/@nonexistent", "@nonexistent"),
    ("@nonexistent", "@nonexistent"),
    ("nonexistent", "nonexistent")
])
def test_resolve_handle_failure(input_str, expected_handle_arg, mock_youtube_client):
    mock_youtube_client.get_channel_id_for_handle.return_value = None
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.FAILED
    assert result.youtube_channel_id is None
    assert result.input_type in ["HANDLE", "RAW_HANDLE"]
    mock_youtube_client.get_channel_id_for_handle.assert_called_once_with(expected_handle_arg)
    mock_youtube_client.get_channel_id_for_user.assert_not_called()

# 4. Tests for types that NEED search fallback
def test_custom_url_needs_search_fallback(mock_youtube_client):
    """Should correctly identify /c/ URLs as needing search fallback."""
    input_str = "https://www.youtube.com/c/customurl"
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.NEEDS_SEARCH_FALLBACK
    assert result.youtube_channel_id is None
    assert result.input_type == "CUSTOM_URL"
    assert "Custom URL" in result.reason
    mock_youtube_client.get_channel_id_for_user.assert_not_called()
    mock_youtube_client.get_channel_id_for_handle.assert_not_called()

# 5. Test for unrecognized inputs
def test_unrecognized_input_fails(mock_youtube_client):
    """Should fail on completely unrecognized input formats."""
    input_str = "this is just a random sentence that is not a channel"
    result = resolve_youtube_channel(input_str, mock_youtube_client)
    assert result.status == ResolveStatus.FAILED
    assert result.youtube_channel_id is None
    assert result.input_type == "UNKNOWN"
    mock_youtube_client.get_channel_id_for_user.assert_not_called()
    mock_youtube_client.get_channel_id_for_handle.assert_not_called()
