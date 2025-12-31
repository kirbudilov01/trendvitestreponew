import pytest
from unittest.mock import MagicMock, patch, call
from googleapiclient.errors import HttpError
import io

from collector.yt.key_rotator import KeyRotator, NoAvailableKeysError
from collector.yt.safe_execute import safe_execute, PotentiallyFatalHttpError
from collector.yt.client import YouTubeClient

# -- Fixtures --

@pytest.fixture
def mock_google_build():
    """Fixture to mock the googleapiclient.discovery.build function."""
    with patch('collector.yt.client.build') as mock_build:
        # Return a simple mock. The methods will be mocked by the request builder lambda.
        mock_build.return_value = MagicMock()
        yield mock_build

# -- Tests for KeyRotator --

def test_key_rotator_initialization(monkeypatch):
    monkeypatch.setenv("YT_API_KEYS", "key1, key2, key3")
    rotator = KeyRotator()
    assert rotator.total_keys == 3
    assert rotator.get_key() == "key1"

def test_key_rotator_rotate(monkeypatch):
    monkeypatch.setenv("YT_API_KEYS", "key1, key2")
    rotator = KeyRotator()
    assert rotator.get_key() == "key1"
    rotator.rotate()
    assert rotator.get_key() == "key2"

def test_key_rotator_raises_error_when_exhausted(monkeypatch):
    monkeypatch.setenv("YT_API_KEYS", "key1")
    rotator = KeyRotator()
    with pytest.raises(NoAvailableKeysError):
        rotator.rotate()

def test_key_rotator_no_keys_env_raises_error():
    with pytest.raises(ValueError):
        KeyRotator()

# -- Tests for safe_execute --

def test_safe_execute_success():
    mock_request = MagicMock(return_value={"status": "ok"})
    result = safe_execute(mock_request)
    assert result == {"status": "ok"}
    mock_request.assert_called_once()

@patch('time.sleep')
def test_safe_execute_retries_on_5xx(mock_sleep):
    mock_response = MagicMock()
    mock_response.status = 503
    error = HttpError(mock_response, b'{"error": {"errors": [{"reason": "backendError"}]}}')
    mock_request = MagicMock(side_effect=[error, error, {"status": "ok"}])

    result = safe_execute(mock_request)

    assert result == {"status": "ok"}
    assert mock_request.call_count == 3
    mock_sleep.assert_has_calls([call(1.0), call(2.0)])

def test_safe_execute_raises_on_quota_error():
    mock_response = MagicMock()
    mock_response.status = 403
    error = HttpError(mock_response, b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}')
    mock_request = MagicMock(side_effect=error)

    with pytest.raises(HttpError) as excinfo:
        safe_execute(mock_request)
    assert excinfo.value.resp.status == 403

def test_safe_execute_raises_on_fatal_4xx():
    mock_response = MagicMock()
    mock_response.status = 404
    error = HttpError(mock_response, b'{"error": {"errors": [{"reason": "notFound"}]}}')
    mock_request = MagicMock(side_effect=error)

    with pytest.raises(PotentiallyFatalHttpError):
        safe_execute(mock_request)

# -- Tests for YouTubeClient Integration --

def test_youtube_client_init(monkeypatch, mock_google_build):
    monkeypatch.setenv("YT_API_KEYS", "key1, key2")
    client = YouTubeClient()
    mock_google_build.assert_called_once_with("youtube", "v3", developerKey="key1", cache_discovery=False)
    assert client is not None

@patch('collector.yt.client.safe_execute')
def test_youtube_client_channels_list_success(mock_safe_execute, monkeypatch, mock_google_build):
    monkeypatch.setenv("YT_API_KEYS", "key1")
    mock_safe_execute.return_value = {"items": [{"id": "UC123"}]}
    client = YouTubeClient()

    result = client.channels_list(part="id", forUsername="test")

    assert result == {"items": [{"id": "UC123"}]}
    # Check that safe_execute was called
    mock_safe_execute.assert_called_once()

@patch('collector.yt.client.safe_execute')
def test_youtube_client_rotates_key_on_quota_error(mock_safe_execute, monkeypatch, mock_google_build):
    monkeypatch.setenv("YT_API_KEYS", "key1, key2, key3")

    # Simulate a quota error on the first call, then success
    mock_response = MagicMock()
    mock_response.status = 403
    quota_error = HttpError(mock_response, b'{}')
    # Manually attach the expected error_details structure
    quota_error.error_details = [{'reason': 'quotaExceeded'}]
    mock_safe_execute.side_effect = [quota_error, {"items": [{"id": "UC_SUCCESS"}]}]

    client = YouTubeClient()
    result = client.channels_list(part="id", forUsername="test")

    # Assertions
    assert result is not None
    assert result["items"][0]["id"] == "UC_SUCCESS"
    assert mock_safe_execute.call_count == 2

    # Check that 'build' was called twice with different keys
    mock_google_build.assert_has_calls([
        call("youtube", "v3", developerKey="key1", cache_discovery=False),
        call("youtube", "v3", developerKey="key2", cache_discovery=False)
    ], any_order=True)

@patch('collector.yt.client.safe_execute')
def test_youtube_client_returns_none_if_all_keys_fail(mock_safe_execute, monkeypatch, mock_google_build):
    monkeypatch.setenv("YT_API_KEYS", "key1, key2")

    mock_response = MagicMock()
    mock_response.status = 403
    quota_error = HttpError(mock_response, b'{}')
    quota_error.error_details = [{'reason': 'dailyLimitExceeded'}]
    mock_safe_execute.side_effect = [quota_error, quota_error] # Fails for both keys

    client = YouTubeClient()
    result = client.channels_list(part="id", id="some_id")

    assert result is None
    assert mock_safe_execute.call_count == 2
    assert mock_google_build.call_count == 2
