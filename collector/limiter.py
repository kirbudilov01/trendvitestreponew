import time
from .redis_client import redis_client

class RateLimiter:
    def __init__(self, client, key: str, limit: int, period: int):
        self.client = client
        self.key = key
        self.limit = limit
        self.period = period

    def is_allowed(self) -> bool:
        """
        Checks if a request is allowed under the rate limit.
        """
        current_time = time.time()
        # Remove timestamps older than the current time window
        self.client.zremrangebyscore(self.key, 0, current_time - self.period)
        # Add the current request timestamp
        self.client.zadd(self.key, {current_time: current_time})
        # Count the number of requests in the current window
        request_count = self.client.zcard(self.key)
        return request_count <= self.limit

def throttle(key: str, limit: int, period: int):
    """
    A simple throttle function that uses the shared Redis client.
    """
    limiter = RateLimiter(redis_client, key, limit, period)
    while not limiter.is_allowed():
        time.sleep(1)

