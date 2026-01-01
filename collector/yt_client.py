import asyncio
import logging
import os
import random
from collections import deque
from time import time
from typing import Deque, Dict, List, Optional

import googleapiclient.discovery
from googleapiclient.errors import HttpError
from collector.limiter import throttle

logger = logging.getLogger(__name__)

# Based on production code
# https://github.com/googleapis/google-api-python-client/blob/main/docs/thread_safety.md
#
# Client is NOT thread-safe, so we need to create a new one for each async task.
# This is a lightweight object.
def build_youtube_client(api_key: str) -> googleapiclient.discovery.Resource:
    return googleapiclient.discovery.build(
        "youtube", "v3", developerKey=api_key, cache_discovery=False
    )


class YouTubeClientRotator:
    def __init__(self, api_keys: List[str], cooldown_time: int = 60):
        if not api_keys:
            raise ValueError("At least one API key is required")
        self._api_keys: Deque[str] = deque(api_keys)
        self._cooldown_keys: Dict[str, float] = {}  # key -> cooldown_end_time
        self._cooldown_time = cooldown_time
        self._lock = asyncio.Lock()

    async def _get_key(self) -> str:
        async with self._lock:
            # First, check for any keys that have finished their cooldown
            now = time()
            for key, cooldown_end in list(self._cooldown_keys.items()):
                if now >= cooldown_end:
                    self._api_keys.append(key)
                    del self._cooldown_keys[key]

            # Find the first available key
            for _ in range(len(self._api_keys)):
                key = self._api_keys[0]
                if key not in self._cooldown_keys:
                    self._api_keys.rotate(-1)  # Move key to the end for rotation
                    return key
                self._api_keys.rotate(-1)

            raise RuntimeError("No available API keys. All are in cooldown.")

    async def _cooldown_key(self, key: str):
        async with self._lock:
            self._cooldown_keys[key] = time() + self._cooldown_time
            # Immediately remove from the active deque
            if key in self._api_keys:
                self._api_keys.remove(key)

    async def safe_execute(self, owner_id: str, func, **kwargs):
        # Throttle requests per user
        await throttle(user_id=owner_id)

        while True:
            api_key = await self._get_key()
            try:
                # Client is not thread-safe, create a new one for each call
                youtube = build_youtube_client(api_key)
                logger.info(f"Executing API call for owner {owner_id} with key ending in ...{api_key[-4:]}")
                return await asyncio.to_thread(func, youtube=youtube, **kwargs)

            except HttpError as e:
                is_quota_error = "quotaExceeded" in str(
                    e.content
                ) or "dailyLimitExceeded" in str(e.content)

                if is_quota_error:
                    logger.warning(
                        f"Quota error with key ...{api_key[-4:]}. Putting it on cooldown."
                    )
                    await self._cooldown_key(api_key)
                    # Try next key immediately
                    continue
                else:
                    # For other HTTP errors, re-raise
                    logger.error(f"API call failed with non-quota error: {e}")
                    raise
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                raise


def get_yt_client() -> "YouTubeClientRotator":
    api_keys_str = os.environ.get("YT_API_KEYS")
    if not api_keys_str:
        raise ValueError("YT_API_KEYS environment variable not set")

    api_keys = [key.strip() for key in api_keys_str.split(",")]
    return YouTubeClientRotator(api_keys=api_keys)
