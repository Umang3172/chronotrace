"""N07 threading_race: a real race, but in threads — deliberately out of scope.

ChronoTrace supports Python asyncio only (spec 19.1), because the event loop's
ready queue is the only tractable forced-scheduling control point in CPython.
Threading is detected so the system can refuse it, not repair it.
"""

import threading
import time

import pytest

COUNTER = {"value": 0}


def increment(times: int) -> None:
    """Increment a shared counter without holding a lock."""
    for _ in range(times):
        current = COUNTER["value"]
        time.sleep(0)
        COUNTER["value"] = current + 1


@pytest.mark.parametrize("workers", [4])
def test_counter_reaches_total(workers: int) -> None:
    COUNTER["value"] = 0
    threads = [threading.Thread(target=increment, args=(500,)) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert COUNTER["value"] == workers * 500
