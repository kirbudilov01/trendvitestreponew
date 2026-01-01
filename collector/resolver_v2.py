import logging
import re
from urllib.parse import urlparse, unquote
from .models import ResolveResult
from .yt_client import YouTubeClientRotator

logger = logging.getLogger(__name__)

# Regex to find a YouTube channel ID (UC...)
RE_CHANNEL_ID = re.compile(r"(UC[a-zA-Z0-9_-]{22})")

# Regex to find a handle (@...)
RE_HANDLE = re.compile(r"(@[a-zA-Z0-9_.-]+)")


def _api_list_channels_by_handle(youtube, forHandle: str, **kwargs):
    """Wrapper for YouTube API channels().list(forHandle=...) call."""
    return youtube.channels().list(forHandle=forHandle, **kwargs).execute()


async def resolve_youtube_channel_id(
    input_str: str, owner_id: int, youtube_client: YouTubeClientRotator
) -> ResolveResult:
    """
    Resolves a YouTube channel ID from various input formats.
    """
    input_str = input_str.strip()

    # 1. Direct Channel ID match (UC...)
    match = RE_CHANNEL_ID.search(input_str)
    if match:
        channel_id = match.group(1)
        logger.info(f"Resolved '{input_str}' directly to channel ID: {channel_id}")
        return ResolveResult(youtube_channel_id=channel_id)

    # 2. Handle match (@handle)
    handle_match = RE_HANDLE.search(input_str)
    # Handle URL paths like /c/..., /user/..., or bare handles that are part of a URL
    if not handle_match:
        try:
            parsed_url = urlparse(input_str)
            if parsed_url.netloc in ["youtube.com", "www.youtube.com"]:
                path_parts = [part for part in unquote(parsed_url.path).split('/') if part]

                if not path_parts:
                    # Just youtube.com, needs fallback
                    return ResolveResult(needs_search_fallback=True)

                # Case: /c/Name or /user/Name
                if path_parts[0] in ['c', 'user'] and len(path_parts) > 1:
                    logger.info(f"'{input_str}' is a legacy /c/ or /user/ URL. Marking for search fallback.")
                    return ResolveResult(needs_search_fallback=True, username=path_parts[1])

                # Case: /@handle
                if path_parts[0].startswith('@'):
                    handle_match = RE_HANDLE.search(path_parts[0])

                # Case: /barehandle (without @)
                elif len(path_parts) == 1 and not path_parts[0] == 'channel':
                    handle_match = RE_HANDLE.search(f"@{path_parts[0]}")

        except Exception:
            pass # Ignore parsing errors

    if handle_match:
        handle = handle_match.group(1)
        try:
            logger.info(f"Attempting to resolve handle '{handle}' via API...")
            response = await youtube_client.safe_execute(
                owner_id=owner_id,
                func=_api_list_channels_by_handle,
                forHandle=handle.lstrip('@'), # The API expects the handle without the '@'
                part="id",
                maxResults=1,
            )
            if response and "items" in response and len(response["items"]) > 0:
                channel_id = response["items"][0]["id"]
                logger.info(f"Resolved handle '{handle}' to channel ID: {channel_id}")
                return ResolveResult(youtube_channel_id=channel_id, username=handle)
            else:
                logger.warning(f"Handle '{handle}' not found via API.")
                # If a handle lookup fails, it's a definitive "not found".
                # No need for search fallback.
                return ResolveResult(error=f"Handle '{handle}' not found.")
        except Exception as e:
            logger.exception(f"Error resolving handle '{handle}': {e}")
            return ResolveResult(error=str(e))

    # 3. If no cheap method works, mark for expensive search fallback
    logger.info(f"Could not resolve '{input_str}' with cheap methods. Marking for search fallback.")
    return ResolveResult(needs_search_fallback=True)
