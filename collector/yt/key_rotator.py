import os
import logging
from typing import List

logger = logging.getLogger(__name__)

class NoAvailableKeysError(Exception):
    """Custom exception raised when all API keys have been exhausted."""
    pass

class KeyRotator:
    """
    Manages a list of YouTube API keys, providing the current key
    and rotating to the next one when requested.
    """
    def __init__(self):
        keys_str = os.environ.get("YT_API_KEYS")
        if not keys_str:
            raise ValueError("YT_API_KEYS environment variable is not set or empty.")

        self.api_keys: List[str] = [key.strip() for key in keys_str.split(',') if key.strip()]
        if not self.api_keys:
            raise ValueError("No valid API keys found in YT_API_KEYS.")

        self._current_index: int = 0
        self.total_keys: int = len(self.api_keys)
        logger.info(f"KeyRotator initialized with {self.total_keys} API keys.")

    def get_key(self) -> str:
        """Returns the current API key."""
        return self.api_keys[self._current_index]

    def rotate(self):
        """
        Rotates to the next API key.

        Raises:
            NoAvailableKeysError: If all keys have been tried and failed.
        """
        self._current_index += 1
        if self._current_index >= self.total_keys:
            logger.critical("All API keys have been exhausted.")
            raise NoAvailableKeysError("All YouTube API keys have failed.")

        logger.warning(f"Rotating to next API key (index {self._current_index}).")

    def reset(self):
        """Resets the rotator to the first key."""
        self._current_index = 0
        logger.info("KeyRotator has been reset to the first key.")
