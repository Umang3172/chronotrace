"""R01 unawaited_writer: a background task writes shared state the test reads.

Seeded race. The writer task and the reader both start after a jittered I/O
delay, so which of them touches ``STORE`` first varies between runs.
"""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

STORE: dict[str, str] = {}


@operation("commit_value", resource="store.value", access="write")
async def commit_value(value: str) -> None:
    """Publish ``value`` into the shared store."""
    STORE["value"] = value


@operation("read_value", resource="store.value", access="read")
async def read_value() -> str | None:
    """Read the shared store."""
    return STORE.get("value")


async def writer_task() -> None:
    """Simulate a producer that commits after some I/O."""
    await io_latency()
    await commit_value("ready")


@pytest.mark.asyncio
async def test_reader_sees_committed_value() -> None:
    STORE.clear()
    task = asyncio.create_task(writer_task())
    await io_latency()
    observed = await read_value()
    with assertion("store.value"):
        assert observed == "ready"
    await task
