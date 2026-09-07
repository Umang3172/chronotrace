"""R14 batch_completion_lifecycle: the assertion depends on a task *finishing*.

A different shape from R01-R06. Those are read-after-write on a single value,
where signalling the write is enough. Here the worker publishes three items and
the assertion depends on all of them, so an event signalled by the write is
*not* enough: the reader would wake after the first item and still fail. The
correct repair is to await the task handle the test already holds, before the
assertion rather than after it.

This case exists to test whether a repair pattern is selected from the evidence
or from the shape the rest of the corpus happens to have.
"""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

BATCH: list[str] = []
EXPECTED = ["alpha", "beta", "gamma"]


@operation("record_item", resource="batch.items", access="write")
async def record_item(item: str) -> None:
    """Publish one item into the batch."""
    BATCH.append(item)


@operation("read_batch", resource="batch.items", access="read")
async def read_batch() -> list[str]:
    """Read everything published so far."""
    return list(BATCH)


async def batch_worker() -> None:
    """Publish every item, each after its own round trip."""
    for item in EXPECTED:
        await io_latency(0.9)
        await record_item(item)


@pytest.mark.asyncio
async def test_batch_is_complete() -> None:
    BATCH.clear()
    handle = asyncio.create_task(batch_worker())
    await io_latency(2.2)
    observed = await read_batch()
    with assertion("batch.items"):
        assert observed == EXPECTED
    await handle
