import asyncio
import logging
import os
import random
from collections import deque
from time import time
from typing import Deque, Dict, List, Any

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from .limiter import throttle

logger = logging.getLogger(__name__)

def build_youtube_client(api_key: str) -> googleapiclient.discovery.Resource:
    return googleapiclient.discovery.build(
        "youtube", "v3", developerKey=api_key, cache_discovery=False
    )

class YouTubeClient:
    def __init__(self, api_keys: List[str], cooldown_time: int = 60):
        if not api_keys:
            raise ValueError("At least one API key is required")
        self._api_keys: Deque[str] = deque(api_keys)
        self._cooldown_keys: Dict[str, float] = {}
        self._cooldown_time = cooldown_time
        self._lock = asyncio.Lock()

    async def _get_key(self) -> str:
        async with self._lock:
            now = time()
            for key, cooldown_end in list(self._cooldown_keys.items()):
                if now >= cooldown_end:
                    self._api_keys.append(key)
                    del self._cooldown_keys[key]

            if not self._api_keys:
                raise RuntimeError("No available API keys. All are in cooldown.")

            key = self._api_keys[0]
            self._api_keys.rotate(-1)
            return key

    async def _cooldown_key(self, key: str):
        async with self._lock:
            self._cooldown_keys[key] = time() + self._cooldown_time
            if key in self._api_keys:
                self._api_keys.remove(key)

    async def _safe_execute(self, owner_id: str, func, max_retries: int = 5, **kwargs) -> Any:
        await throttle(user_id=owner_id)
        last_exception = None
        for attempt in range(max_retries):
            api_key = await self._get_key()
            try:
                youtube = build_youtube_client(api_key)
                return await asyncio.to_thread(func, youtube=youtube, **kwargs)
            except HttpError as e:
                last_exception = e
                if "quotaExceeded" in str(e.content) or "dailyLimitExceeded" in str(e.content):
                    await self._cooldown_key(api_key)
                    continue
                if e.status_code == 429 or e.status_code >= 500:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                last_exception = e
                break
        raise last_exception or RuntimeError("API call failed after all retries")

    async def get_channel_by_handle(self, owner_id: str, handle: str) -> Any:
        handle = handle.lstrip('@')
        return await self._safe_execute(
            owner_id,
            lambda youtube, **kwargs: youtube.channels().list(**kwargs).execute(),
            forHandle=handle,
            part="id",
            maxResults=1,
        )

def get_yt_client() -> "YouTubeClient":
    api_keys_str = os.environ.get("YT_API_KEYS")
    if not api_keys_str:
        raise ValueError("YT_API_KEYS environment variable not set")
    api_keys = [key.strip() for key in api_keys_str.split(",")]
    return YouTubeClient(api_keys=api_keys)

youtube_client = get_yt_client()
