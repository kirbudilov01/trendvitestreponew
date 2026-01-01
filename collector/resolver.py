import logging
import re
from enum import Enum
from typing import NamedTuple

from .yt.client import youtube_client

logger = logging.getLogger(__name__)

RE_CHANNEL_ID = re.compile(r"(UC[a-zA-Z0-9_-]{22})")
RE_HANDLE = re.compile(r"(@[a-zA-Z0-9_.-]+)")

class ResolveStatus(Enum):
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"

class ResolveResult(NamedTuple):
    status: ResolveStatus
    youtube_channel_id: str | None = None
    error: str | None = None

async def resolve_youtube_channel(input_str: str, owner_id: int) -> ResolveResult:
    input_str = input_str.strip()

    # 1. Direct Channel ID match
    match = RE_CHANNEL_ID.search(input_str)
    if match:
        channel_id = match.group(1)
        return ResolveResult(status=ResolveStatus.RESOLVED, youtube_channel_id=channel_id)

    # 2. Handle match
    handle_match = RE_HANDLE.search(input_str)
    if handle_match:
        handle = handle_match.group(1)
        try:
            response = await youtube_client.get_channel_by_handle(owner_id, handle)
            if response and "items" in response and len(response["items"]) > 0:
                channel_id = response["items"][0]["id"]
                return ResolveResult(status=ResolveStatus.RESOLVED, youtube_channel_id=channel_id)
            else:
                return ResolveResult(status=ResolveStatus.FAILED, error=f"Handle '{handle}' not found.")
        except Exception as e:
            logger.exception(f"Error resolving handle '{handle}': {e}")
            return ResolveResult(status=ResolveStatus.FAILED, error=str(e))

    return ResolveResult(status=ResolveStatus.FAILED, error="Could not resolve input.")
