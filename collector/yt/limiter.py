import time
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    A simple rate limiter to ensure a minimum delay between operations.
    """
    def __init__(self, requests_per_second: float = 2.0):
        if requests_per_second <= 0:
            raise ValueError("Requests per second must be positive.")
        self.min_interval = 1.0 / requests_per_second
        self.last_call_time = 0
        logger.info(f"RateLimiter initialized to ~{requests_per_second:.1f} RPS "
                    f"(~{self.min_interval:.2f}s interval).")

    def wait(self):
        """
        Blocks execution until the minimum interval since the last call has passed.
        """
        if self.last_call_time == 0:
            self.last_call_time = time.monotonic()
            return

        elapsed = time.monotonic() - self.last_call_time
        wait_time = self.min_interval - elapsed

        if wait_time > 0:
            # logger.debug(f"Rate limiting: waiting for {wait_time:.2f} seconds.")
            time.sleep(wait_time)

        self.last_call_time = time.monotonic()
