import time
import logging
from typing import Callable, Dict, Any

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Configurable retry settings
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_FACTOR = 2.0

class PotentiallyFatalHttpError(HttpError):
    """
    Custom exception to wrap non-retriable HTTP errors for clearer upstream handling.
    """
    pass

def safe_execute(request_func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Safely executes a YouTube API request with retry logic for specific errors.

    Args:
        request_func: A zero-argument function that, when called, executes the
                      googleapiclient request and returns the result.

    Returns:
        The API response dictionary.

    Raises:
        HttpError: If a quota-related (403) error occurs.
        PotentiallyFatalHttpError: For non-retriable client-side errors (e.g., 400, 404).
        HttpError: If retries are exhausted for server-side errors (5xx).
    """
    retries = 0
    backoff = INITIAL_BACKOFF

    while retries < MAX_RETRIES:
        try:
            return request_func()
        except HttpError as e:
            error_details = e.error_details
            status_code = e.resp.status

            # Case 1: Quota errors (403). Do not retry here. Let the client handle key rotation.
            if status_code == 403 and any(
                err.get("reason") in ["quotaExceeded", "dailyLimitExceeded", "userRateLimitExceeded"]
                for err in error_details
            ):
                logger.warning(f"Quota error encountered: {error_details[0].get('reason')}. Propagating up.")
                raise e # Re-raise to be caught by the client for key rotation

            # Case 2: "Too Many Requests" (429) or Server-side errors (5xx). Retry with backoff.
            if status_code == 429 or status_code >= 500:
                retries += 1
                if retries >= MAX_RETRIES:
                    logger.error(f"Request failed after {MAX_RETRIES} retries. Raising final HttpError.")
                    raise e

                reason = error_details[0].get('reason') if error_details else "N/A"
                logger.warning(
                    f"Request failed with status {status_code} (reason: {reason}). "
                    f"Retrying in {backoff:.2f} seconds... (Attempt {retries}/{MAX_RETRIES})"
                )
                time.sleep(backoff)
                backoff *= BACKOFF_FACTOR
                continue

            # Case 3: Other client-side errors (e.g., 400, 404). Do not retry.
            logger.error(f"Non-retriable client error encountered: {status_code}. Details: {error_details}")
            raise PotentiallyFatalHttpError(e.resp, e.content, uri=e.uri) from e

    # This line should not be reachable, but is here for safety.
    raise Exception("Exited retry loop unexpectedly in safe_execute.")
