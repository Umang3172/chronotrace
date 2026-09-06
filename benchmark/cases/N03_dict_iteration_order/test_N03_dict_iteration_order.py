"""N03 dict_iteration_order: a negative control. Ordering comes from hashing, not scheduling.

Under ChronoTrace's determinism protocol ``PYTHONHASHSEED`` is pinned for every
captured run, which makes this test deterministic rather than flaky. It never
produces a pass/fail pair, so the pipeline refuses it at the trace-pair stage
(E1) instead of inventing a race.
"""

import pytest

from chronotrace.capture.instrument import assertion, operation

TAGS = {"alpha", "beta", "gamma", "delta", "epsilon"}
SEEN: list[str] = []


@operation("collect_tags", resource="tags.order", access="write")
async def collect_tags() -> None:
    """Materialise the tag set in iteration order."""
    SEEN.extend(TAGS)


@operation("read_tags", resource="tags.order", access="read")
async def read_tags() -> list[str]:
    """Read the materialised tag order."""
    return list(SEEN)


@pytest.mark.asyncio
async def test_first_tag_is_alpha() -> None:
    SEEN.clear()
    await collect_tags()
    order = await read_tags()
    with assertion("tags.order"):
        assert order[0] == "alpha"
