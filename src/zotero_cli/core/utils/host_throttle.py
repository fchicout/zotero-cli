"""A process-wide, thread-safe pacing of requests per host (Issue #715, from #611).

Each client used to pace itself: read when its last request was, sleep, write the time back,
without a lock, so two threads could both read the same value and fire together, and two
clients of one provider did not know about each other. Here the caller reserves its slot under
a lock (the previous request's slot plus the interval) and sleeps outside it, so requests to a
host leave at least `interval` apart however many callers there are."""

import threading
import time
from typing import Callable, Dict
from urllib.parse import urlparse


class HostThrottle:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_slot: Dict[str, float] = {}

    def wait(self, host: str, interval: float) -> float:
        """Blocks until a request to `host` may go out, keeping `interval` seconds between
        requests to it. The first one goes at once. Returns the seconds it waited."""
        if interval <= 0:
            return 0.0
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot.get(host, now))
            self._next_slot[host] = slot + interval
        delay = slot - now
        if delay > 0:
            (self._sleep or time.sleep)(delay)
        return max(delay, 0.0)

    def reset(self) -> None:
        """Forgets every host (tests, so one test's requests do not pace the next)."""
        with self._lock:
            self._next_slot.clear()


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower() or url


HOST_THROTTLE = HostThrottle()
