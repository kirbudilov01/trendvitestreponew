import os

class AppConfig:
    # URL for general Redis connections (e.g., locks, limiters)
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # URL specifically for Celery message broker
    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")

settings = AppConfig()
