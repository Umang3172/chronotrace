"""N06 wrong_assertion: a negative control. The test is simply incorrect.

It fails every time. A test that always fails is not flaky, and ChronoTrace has
no pass trace to diff against.
"""

import pytest

from chronotrace.capture.instrument import assertion, operation

TOTALS: dict[str, int] = {}


@operation("compute_total", resource="cart.total", access="write")
async def compute_total() -> None:
    """Compute the cart total from two line items."""
    TOTALS["total"] = 3 + 4


@operation("read_total", resource="cart.total", access="read")
async def read_total() -> int:
    """Read the computed total."""
    return TOTALS["total"]


@pytest.mark.asyncio
async def test_cart_total() -> None:
    await compute_total()
    total = await read_total()
    with assertion("cart.total"):
        assert total == 8
