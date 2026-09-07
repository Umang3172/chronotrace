"""R06 queue_consumer_early: the consumer drains the queue before the producer enqueues."""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

QUEUE: list[str] = []


@operation("enqueue_job", resource="queue.items", access="write")
async def enqueue_job(job: str) -> None:
    """Append a job to the work queue."""
    QUEUE.append(job)


@operation("drain_queue", resource="queue.items", access="read")
async def drain_queue() -> list[str]:
    """Take everything currently queued."""
    taken = list(QUEUE)
    QUEUE.clear()
    return taken


async def producer() -> None:
    """Enqueue one job once its payload has been fetched."""
    await io_latency()
    await enqueue_job("job-1")


@pytest.mark.asyncio
async def test_consumer_drains_produced_job() -> None:
    QUEUE.clear()
    task = asyncio.create_task(producer())
    await io_latency()
    drained = await drain_queue()
    with assertion("queue.items"):
        assert drained == ["job-1"]
    await task
