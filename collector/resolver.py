import re
import logging
from typing import Optional
from pydantic import BaseModel
from enum import Enum

# Updated import path
from .yt.client import YouTubeClient

logger = logging.getLogger(__name__)

# Regex patterns remain the same
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


def _get_channel_id_from_response(response: Optional[dict]) -> Optional[str]:
    """Helper to safely extract channel ID from a channels.list response."""
    if response and "items" in response and len(response["items"]) > 0:
        return response["items"][0].get("id")
    return None


def resolve_youtube_channel(input_str: str, client: YouTubeClient) -> ResolveResult:
    """
    Resolves a YouTube channel input string to a 'UC...' channel ID using the new client.
    """
    input_str = input_str.strip()
    logger.info(f"Attempting to resolve input: '{input_str}'")

    # 1. Direct Channel ID (UC...) - No change
    match = RE_CHANNEL_ID.search(input_str)
    if match:
        channel_id = match.group(1)
        logger.info(f"Found direct channel ID '{channel_id}' in input.")
        return ResolveResult(
            status=ResolveStatus.RESOLVED, youtube_channel_id=channel_id,
            input_str=input_str, input_type="CHANNEL_ID"
        )

    # 2. User URL (/user/...) - Use new client method
    match = RE_USER.search(input_str)
    if match:
        username = match.group(1)
        logger.info(f"Detected user URL with username: '{username}'. Attempting API call.")
        response = client.channels_list(part="id", forUsername=username)
        channel_id = _get_channel_id_from_response(response)

        if channel_id:
            return ResolveResult(
                status=ResolveStatus.RESOLVED, youtube_channel_id=channel_id,
                input_str=input_str, input_type="USER_URL"
            )
        else:
            return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason=f"API call for username '{username}' failed or returned no result.",
                input_type="USER_URL"
            )

    # 3. Handle URL (/@...) - Use new client method
    match = RE_HANDLE.search(input_str)
    if match:
        handle = match.group(1).lstrip('@')
        logger.info(f"Detected handle URL with handle: '{handle}'. Attempting API call.")
        response = client.channels_list(part="id", forHandle=handle)
        channel_id = _get_channel_id_from_response(response)

        if channel_id:
            return ResolveResult(
                status=ResolveStatus.RESOLVED, youtube_channel_id=channel_id,
                input_str=input_str, input_type="HANDLE"
            )
        else:
            return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason=f"API call for handle '{handle}' failed or returned no result.",
                input_type="HANDLE"
            )

    # 4. Custom URL (/c/...) - No change, still needs fallback
    match = RE_CUSTOM_URL.search(input_str)
    if match:
        custom_name = match.group(1)
        return ResolveResult(
            status=ResolveStatus.NEEDS_SEARCH_FALLBACK,
            input_str=input_str,
            reason=f"Custom URL '/c/{custom_name}' requires a search API call.",
            input_type="CUSTOM_URL"
        )

    # 5. Raw Handle - Use new client method
    match = RE_RAW_HANDLE.search(input_str)
    if match:
        if len(input_str) > 70 or " " in input_str:
            return ResolveResult(status=ResolveStatus.FAILED, input_str=input_str,
                                 reason="Unrecognized input format.", input_type="UNKNOWN")

        handle = match.group(1).lstrip('@')
        logger.info(f"Detected raw handle '{handle}'. Attempting API call.")
        response = client.channels_list(part="id", forHandle=handle)
        channel_id = _get_channel_id_from_response(response)

        if channel_id:
            return ResolveResult(
                status=ResolveStatus.RESOLVED, youtube_channel_id=channel_id,
                input_str=input_str, input_type="RAW_HANDLE"
            )
        else:
            return ResolveResult(
                status=ResolveStatus.FAILED,
                input_str=input_str,
                reason=f"API call for raw handle '{handle}' failed or returned no result.",
                input_type="RAW_HANDLE"
            )

    return ResolveResult(
        status=ResolveStatus.FAILED, input_str=input_str,
        reason="Unrecognized input format.", input_type="UNKNOWN"
    )
