import os
import logging
from typing import Optional, List

from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class YouTubeClient:
    """
    Базовый клиент для работы с YouTube Data API v3.
    На данном этапе не включает ротацию ключей или ретраи.
    """
    def __init__(self, api_keys: Optional[List[str]] = None):
        if api_keys:
            self.api_keys = api_keys
        else:
            keys_str = os.environ.get("YT_API_KEYS")
            if not keys_str:
                raise ValueError("YT_API_KEYS environment variable is not set.")
            self.api_keys = [key.strip() for key in keys_str.split(',')]

        if not self.api_keys:
            raise ValueError("No API keys provided for YouTubeClient.")

        self._api_key_index = 0
        self.youtube_service = self._build_service()

    def _build_service(self) -> Resource:
        """Строит объект сервиса YouTube API."""
        api_key = self.api_keys[self._api_key_index]
        return build("youtube", "v3", developerKey=api_key)

    def get_channel_id_for_user(self, username: str) -> Optional[str]:
        """
        Получает 'UC...' ID канала по его 'custom URL' (/user/...).
        Это "дешевый" запрос, который стоит 1 единицу квоты.
        """
        try:
            request = self.youtube_service.channels().list(
                part="id",
                forUsername=username
            )
            response = request.execute()

            if response and "items" in response and len(response["items"]) > 0:
                channel_id = response["items"][0].get("id")
                logger.info(f"Successfully resolved username '{username}' to channel ID '{channel_id}'.")
                return channel_id
            else:
                logger.warning(f"Could not find channel for username: {username}")
                return None
        except HttpError as e:
            logger.error(f"HTTP error while fetching channel for username '{username}': {e}")
            return None
        except Exception as e:
            logger.exception(f"An unexpected error occurred while fetching channel for username '{username}': {e}")
            return None

    def get_channel_id_for_handle(self, handle: str) -> Optional[str]:
        """
        Получает 'UC...' ID канала по его handle (@...).
        Это "дешевый" запрос, который стоит 1 единицу квоты.
        """
        # API ожидает handle без символа "@"
        if handle.startswith('@'):
            handle = handle[1:]

        try:
            request = self.youtube_service.channels().list(
                part="id",
                forHandle=handle
            )
            response = request.execute()

            if response and "items" in response and len(response["items"]) > 0:
                channel_id = response["items"][0].get("id")
                logger.info(f"Successfully resolved handle '{handle}' to channel ID '{channel_id}'.")
                return channel_id
            else:
                logger.warning(f"Could not find channel for handle: {handle}")
                return None
        except HttpError as e:
            # Ручка forHandle - новая, и может вернуть 400, если handle не существует.
            # Это ожидаемое поведение, а не системная ошибка.
            if e.resp.status == 400:
                 logger.warning(f"API returned 400 for handle '{handle}', likely does not exist.")
            else:
                logger.error(f"HTTP error while fetching channel for handle '{handle}': {e}")
            return None
        except Exception as e:
            logger.exception(f"An unexpected error occurred while fetching channel for handle '{handle}': {e}")
            return None
