"""R05 event_set_after_wait: a readiness flag is published on the wrong side of the I/O."""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

BROKER: dict[str, object] = {}


@operation("publish_ready", resource="broker.ready", access="write")
async def publish_ready() -> None:
    """Mark the broker as ready to accept subscribers."""
    BROKER["ready"] = True


@operation("subscribe", resource="broker.ready", access="read")
async def subscribe() -> bool:
    """Subscribe, which is only valid once the broker is ready."""
    return bool(BROKER.get("ready", False))


async def broker_startup() -> None:
    """Start the broker; readiness is published only after the socket binds."""
    await io_latency()
    await publish_ready()


@pytest.mark.asyncio
async def test_subscriber_waits_for_ready() -> None:
    BROKER.clear()
    startup = asyncio.create_task(broker_startup())
    await io_latency()
    accepted = await subscribe()
    with assertion("broker.ready"):
        assert accepted is True
    await startup
