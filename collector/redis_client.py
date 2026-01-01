import redis
from .config import settings

# Initialize a connection pool
# The decode_responses=True argument ensures that the data read from Redis is decoded into strings
redis_pool = redis.ConnectionPool.from_url(settings.redis_url, max_connections=10, decode_responses=True)

def get_redis_client():
    """
    Returns a Redis client from the connection pool.
    This function ensures that we reuse connections instead of creating new ones for each request.
    """
    return redis.Redis(connection_pool=redis_pool)

# A singleton Redis client instance to be used across the application
redis_client = get_redis_client()
