import redis.asyncio as redis
import os

# Production-ready Redis client provider
# We create a new client for each request to ensure thread-safety
def get_redis_client() -> redis.Redis:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(redis_url, decode_responses=True)
