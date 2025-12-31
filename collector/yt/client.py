import logging
from typing import Dict, Any, List, Optional, Callable

from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from .key_rotator import KeyRotator, NoAvailableKeysError
from .safe_execute import safe_execute, PotentiallyFatalHttpError
from .limiter import RateLimiter

logger = logging.getLogger(__name__)


class YouTubeClient:
    """
    Отказоустойчивый клиент для YouTube Data API v3, включающий:
    - Ротацию API ключей при ошибках квоты.
    - Повторные запросы (retry) с exponential backoff для ошибок сервера.
    - Ограничение частоты запросов (rate limiting).
    """
    def __init__(self, requests_per_second: float = 2.0):
        self.key_rotator = KeyRotator()
        self.limiter = RateLimiter(requests_per_second)
        self.youtube_service: Resource = self._build_service()

    def _build_service(self) -> Resource:
        """Строит объект сервиса, используя текущий ключ из ротатора."""
        api_key = self.key_rotator.get_key()
        logger.info(f"Building YouTube service with new API key.")
        return build("youtube", "v3", developerKey=api_key, cache_discovery=False)

    def _execute_request(self, request_builder: Callable[[Resource], Any]) -> Optional[Dict[str, Any]]:
        """
        Центральный метод для выполнения запросов, который управляет ротацией ключей.
        """
        while True:
            try:
                self.limiter.wait()
                # Мы передаем lambda, чтобы safe_execute мог вызывать ее повторно
                # с одним и тем же объектом запроса.
                request = request_builder(self.youtube_service)
                return safe_execute(lambda: request.execute())

            except HttpError as e:
                # Если это ошибка квоты, пытаемся сменить ключ
                error_details = e.error_details
                is_quota_error = e.resp.status == 403 and any(
                    err.get("reason") in ["quotaExceeded", "dailyLimitExceeded", "userRateLimitExceeded"]
                    for err in error_details
                )
                if is_quota_error:
                    logger.warning("Quota error detected. Attempting to rotate API key.")
                    try:
                        self.key_rotator.rotate()
                        self.youtube_service = self._build_service()
                        continue # Повторяем попытку с новым ключом
                    except NoAvailableKeysError:
                        logger.error("All API keys are exhausted. Cannot proceed.")
                        return None # Ключи закончились, возвращаем None
                else:
                    # Другая HttpError, не связанная с квотой, которую не смог обработать safe_execute
                    logger.exception("An unhandled HttpError occurred.")
                    return None

            except PotentiallyFatalHttpError:
                # safe_execute решил, что ошибка фатальна (например, 400 Bad Request)
                logger.error("A non-retriable HTTP error occurred. Aborting request.")
                return None

            except Exception:
                logger.exception("An unexpected error occurred during request execution.")
                return None

    def channels_list(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к 'channels.list' эндпоинту.
        Пример: client.channels_list(part="snippet,statistics", id="UC...")
        """
        return self._execute_request(
            lambda service: service.channels().list(**kwargs)
        )

    def playlist_items_list(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к 'playlistItems.list' эндпоинту.
        Пример: client.playlist_items_list(part="snippet", playlistId="PL...", maxResults=50)
        """
        return self._execute_request(
            lambda service: service.playlistItems().list(**kwargs)
        )

    def videos_list(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к 'videos.list' эндпоинту.
        Пример: client.videos_list(part="snippet,contentDetails", id="...")
        """
        return self._execute_request(
            lambda service: service.videos().list(**kwargs)
        )
