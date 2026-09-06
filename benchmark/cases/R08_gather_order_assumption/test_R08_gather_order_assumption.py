"""R08 gather_order_assumption: the assertion over-constrains legitimate concurrency.

The correct answer here is **not** to synchronise. Both orderings are valid
completions of two independent tasks; the test is asserting an ordering the
production code never promised. ChronoTrace should say so rather than serialise
two operations that are allowed to interleave.
"""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

COMPLETIONS: list[str] = []


@operation("finish_alpha", resource="completions.order", access="write")
async def finish_alpha() -> None:
    """Record completion of the alpha fetch."""
    COMPLETIONS.append("alpha")


@operation("finish_beta", resource="completions.order", access="write")
async def finish_beta() -> None:
    """Record completion of the beta fetch."""
    COMPLETIONS.append("beta")


@operation("read_completions", resource="completions.order", access="read")
async def read_completions() -> list[str]:
    """Read the completion log."""
    return list(COMPLETIONS)


async def fetch_alpha() -> None:
    """Independent fetch A."""
    await io_latency()
    await finish_alpha()


async def fetch_beta() -> None:
    """Independent fetch B."""
    await io_latency()
    await finish_beta()


@pytest.mark.asyncio
async def test_completion_order_is_alpha_then_beta() -> None:
    COMPLETIONS.clear()
    await asyncio.gather(fetch_alpha(), fetch_beta())
    order = await read_completions()
    with assertion("completions.order"):
        assert order == ["alpha", "beta"]
