"""The process-wide per-host throttle (Issue #715, from #611)."""

import threading
from typing import List

import pytest

from zotero_cli.core.utils.host_throttle import HostThrottle, host_of


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: List[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _throttle() -> "tuple[HostThrottle, _Clock]":
    clock = _Clock()
    return HostThrottle(clock=clock, sleep=clock.sleep), clock


def test_the_first_request_to_a_host_goes_at_once() -> None:
    throttle, clock = _throttle()

    assert throttle.wait("a.test", 1.1) == 0.0
    assert clock.slept == []


def test_the_next_one_waits_for_the_interval() -> None:
    throttle, clock = _throttle()

    throttle.wait("a.test", 1.1)
    waited = throttle.wait("a.test", 1.1)

    assert waited == pytest.approx(1.1)
    assert clock.slept == [pytest.approx(1.1)]


def test_a_request_after_the_interval_does_not_wait() -> None:
    throttle, clock = _throttle()
    throttle.wait("a.test", 1.0)
    clock.now += 5

    assert throttle.wait("a.test", 1.0) == 0.0


def test_hosts_are_independent() -> None:
    throttle, clock = _throttle()
    throttle.wait("a.test", 1.0)

    assert throttle.wait("b.test", 1.0) == 0.0
    assert clock.slept == []


def test_no_interval_means_no_pacing_and_no_slot() -> None:
    throttle, clock = _throttle()

    assert throttle.wait("a.test", 0) == 0.0
    assert throttle.wait("a.test", 0) == 0.0
    assert clock.slept == []


def test_reset_forgets_the_hosts() -> None:
    throttle, _ = _throttle()
    throttle.wait("a.test", 1.0)

    throttle.reset()

    assert throttle.wait("a.test", 1.0) == 0.0


def test_threads_get_distinct_slots_so_requests_never_leave_together() -> None:
    """The read-sleep-write race: two threads read the same last time and both fired. A slot is
    now reserved under the lock, so each of eight callers gets its own, `interval` apart."""
    clock = _Clock()
    throttle = HostThrottle(clock=clock, sleep=lambda _seconds: None)
    waits: List[float] = []
    lock = threading.Lock()

    def go() -> None:
        waited = throttle.wait("a.test", 1.0)
        with lock:
            waits.append(waited)

    threads = [threading.Thread(target=go) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(waits) == [float(n) for n in range(8)]


def test_the_host_is_the_netloc_in_lower_case() -> None:
    assert host_of("https://API.Example.org/graph/v1/paper") == "api.example.org"
