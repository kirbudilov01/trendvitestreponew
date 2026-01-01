import os
import redis.asyncio as redis

# Create a single, shared Redis connection pool
# This avoids creating a new connection for every request, which is inefficient.
redis_pool = redis.ConnectionPool.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379"),
    max_connections=int(os.environ.get("REDIS_MAX_CONNECTIONS", 50)),
    decode_responses=True
)

def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client instance from the shared connection pool.
    """
    return redis.Redis(connection_pool=redis_pool)

# A single client instance can be reused if preferred, as it's thread-safe.
# This avoids the overhead of creating a new client object each time.
shared_redis_client = get_redis_client()
