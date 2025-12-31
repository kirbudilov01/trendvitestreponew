import re
import logging
from typing import Optional
from pydantic import BaseModel
from enum import Enum

from .youtube_client import YouTubeClient

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for efficiency
RE_CHANNEL_ID = re.compile(r"(UC[a-zA-Z0-9_-]{22})")
RE_USER = re.compile(r"/(?:user)/([a-zA-Z0-9_-]+)")
RE_HANDLE = re.compile(r"/(@[a-zA-Z0-9_.-]+)")
RE_CUSTOM_URL = re.compile(r"/(?:c)/([a-zA-Z0-9_-]+)")
RE_RAW_HANDLE = re.compile(r"^(@?[a-zA-Z0-9_.-]+)$")


class ResolveStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NEEDS_SEARCH_FALLBACK = "NEEDS_SEARCH_FALLBACK"
    FAILED = "FAILED"


class ResolveResult(BaseModel):
    status: ResolveStatus
    youtube_channel_id: Optional[str] = None
    input_str: str
    reason: Optional[str] = None
    input_type: Optional[str] = None


def resolve_youtube_channel(input_str: str, client: YouTubeClient) -> ResolveResult:
    """
    Resolves a YouTube channel input string to a 'UC...' channel ID.

    This function prioritizes cheap resolution methods and avoids expensive searches
    in accordance with the PR2 requirements.
    """
    input_str = input_str.strip()
    logger.info(f"Attempting to resolve input: '{input_str}'")

    # 1. Direct Channel ID (UC...) - Most reliable
    match = RE_CHANNEL_ID.search(input_str)
    if match:
        channel_id = match.group(1)
        logger.info(f"Found direct channel ID '{channel_id}' in input.")
        return ResolveResult(
            status=ResolveStatus.RESOLVED,
            youtube_channel_id=channel_id,
            input_str=input_str,
            input_type="CHANNEL_ID"
        )

    # 2. User URL (/user/...) - Requires a cheap API call
    match = RE_USER.search(input_str)
    if match:
        username = match.group(1)
        logger.info(f"Detected user URL with username: '{username}'. Attempting API call.")
        channel_id = client.get_channel_id_for_user(username)
        if channel_id:
            return ResolveResult(
                status=ResolveStatus.RESOLVED,
                youtube_channel_id=channel_id,
                input_str=input_str,
                input_type="USER_URL"
            )
        else:
            return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason=f"API call for username '{username}' failed or returned no result.",
                input_type="USER_URL"
            )

    # 3. Handle URL (/@...) - Requires a cheap API call
    match = RE_HANDLE.search(input_str)
    if match:
        handle = match.group(1)
        logger.info(f"Detected handle URL with handle: '{handle}'. Attempting API call.")
        channel_id = client.get_channel_id_for_handle(handle)
        if channel_id:
            return ResolveResult(
                status=ResolveStatus.RESOLVED,
                youtube_channel_id=channel_id,
                input_str=input_str,
                input_type="HANDLE"
            )
        else:
            # Если API-вызов не дал результата, помечаем как FAILED, т.к. дешевая попытка уже сделана
            return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason=f"API call for handle '{handle}' failed or returned no result.",
                input_type="HANDLE"
            )

    # 4. Custom URL (/c/...) - Requires search, flag for fallback
    match = RE_CUSTOM_URL.search(input_str)
    if match:
        custom_name = match.group(1)
        logger.info(f"Detected custom URL '/c/{custom_name}'. Flagging for search fallback.")
        return ResolveResult(
            status=ResolveStatus.NEEDS_SEARCH_FALLBACK,
            input_str=input_str,
            reason=f"Custom URL '/c/{custom_name}' requires a search API call.",
            input_type="CUSTOM_URL"
        )

    # 5. Raw Handle (e.g., "@handle" or "handle") - Broad catch-all, flag for fallback
    match = RE_RAW_HANDLE.search(input_str)
    if match:
        # Basic sanity check to avoid matching long, random strings
        if len(input_str) > 70 or " " in input_str:
             return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason="Unrecognized input format.",
                input_type="UNKNOWN"
            )

        handle = match.group(1)
        logger.info(f"Detected raw handle '{handle}'. Attempting API call.")
        channel_id = client.get_channel_id_for_handle(handle)
        if channel_id:
            return ResolveResult(
                status=ResolveStatus.RESOLVED,
                youtube_channel_id=channel_id,
                input_str=input_str,
                input_type="RAW_HANDLE"
            )
        else:
            return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason=f"API call for raw handle '{handle}' failed or returned no result.",
                input_type="RAW_HANDLE"
            )

    logger.warning(f"Could not recognize format for input: '{input_str}'")
    return ResolveResult(
        status=ResolveStatus.FAILED,
        input_str=input_str,
        reason="Unrecognized input format.",
        input_type="UNKNOWN"
    )
