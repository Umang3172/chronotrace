"""R12 depth2_two_constraints: failure needs two scheduling constraints at once.

The assertion fails only when *both* reads are stale. Forcing either ordering
alone leaves the other coin-flip in place, so the forced failure rate lands
strictly between 0 and 1 — the signature of a depth-2 bug (spec 13).
"""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

STATE: dict[str, bool] = {}


@operation("set_primary", resource="state.primary", access="write")
async def set_primary() -> None:
    """Publish the primary replica flag."""
    STATE["primary"] = True


@operation("set_secondary", resource="state.secondary", access="write")
async def set_secondary() -> None:
    """Publish the secondary replica flag."""
    STATE["secondary"] = True


@operation("read_primary", resource="state.primary", access="read")
async def read_primary() -> bool:
    """Read the primary flag."""
    return STATE.get("primary", False)


@operation("read_secondary", resource="state.secondary", access="read")
async def read_secondary() -> bool:
    """Read the secondary flag."""
    return STATE.get("secondary", False)


async def primary_replica() -> None:
    """Bring up the primary replica."""
    await io_latency()
    await set_primary()


async def secondary_replica() -> None:
    """Bring up the secondary replica."""
    await io_latency()
    await set_secondary()


@pytest.mark.asyncio
async def test_at_least_one_replica_is_up() -> None:
    STATE.clear()
    tasks = [asyncio.create_task(primary_replica()), asyncio.create_task(secondary_replica())]
    await io_latency()
    primary = await read_primary()
    secondary = await read_secondary()
    with assertion("state.primary"):
        assert primary or secondary
    await asyncio.gather(*tasks)
