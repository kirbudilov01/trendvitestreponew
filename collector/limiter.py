import asyncio
import time
import logging
from collector.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Based on provided production code
async def throttle(user_id: str, max_requests: int = 5, period: int = 1):
    """
    Asynchronous request rate limiter using Redis ZSET.
    """
    redis = get_redis_client()
    key = f"throttle:{user_id}"
    now = time.time()

    # Clean up old timestamps
    await redis.zremrangebyscore(key, 0, now - period)

    # Check current request count
    current_requests = await redis.zcard(key)

    if current_requests < max_requests:
        # Add current timestamp and allow request
        await redis.zadd(key, {str(now): now})
        logger.debug(f"Request allowed for {user_id}. Count: {current_requests + 1}/{max_requests}")
        return

    # If limit is exceeded, calculate wait time
    oldest_timestamp_tuple = await redis.zrange(key, 0, 0, withscores=True)
    if not oldest_timestamp_tuple:
        # Should not happen if current_requests > 0, but as a safeguard
        await redis.zadd(key, {str(now): now})
        return

    oldest_timestamp = oldest_timestamp_tuple[0][1]
    wait_time = (oldest_timestamp + period) - now

    if wait_time > 0:
        logger.warning(f"Rate limit exceeded for {user_id}. Throttling for {wait_time:.2f} seconds.")
        await asyncio.sleep(wait_time)

    # Add current timestamp after waiting
    await redis.zadd(key, {str(time.time()): time.time()})
    await redis.aclose()
