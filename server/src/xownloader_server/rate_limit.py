from collections import defaultdict, deque
from time import monotonic

from xownloader_server.errors import RateLimitExceeded


class RateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_key: str) -> None:
        now = monotonic()
        window = self._requests[client_key]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self.requests_per_minute:
            raise RateLimitExceeded("Rate limit exceeded; retry later")
        window.append(now)