import os

class CeleryConfig:
    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")

settings = CeleryConfig()
