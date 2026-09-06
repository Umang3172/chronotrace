"""N02 network_timeout: a negative control. An external call fails intermittently.

The failure is a raised ``TimeoutError``, not a failed assertion about shared
state. Nothing about the schedule explains it.
"""

import asyncio
import random

import pytest

from chronotrace.capture.instrument import assertion, operation

RESPONSES: list[str] = []


@operation("http_get", resource="upstream.response", access="write")
async def http_get() -> None:
    """Call an upstream service that intermittently times out."""
    await asyncio.sleep(0)
    if random.random() < 0.4:  # noqa: S311
        raise TimeoutError("upstream did not respond in time")
    RESPONSES.append("200 OK")


@operation("read_response", resource="upstream.response", access="read")
async def read_response() -> str:
    """Read the stored upstream response."""
    return RESPONSES[-1]


@pytest.mark.asyncio
async def test_upstream_returns_ok() -> None:
    RESPONSES.clear()
    await http_get()
    body = await read_response()
    with assertion("upstream.response"):
        assert body == "200 OK"
