"""The forced-ordering harness is the load-bearing claim; these tests are its proof."""

import asyncio

import pytest

from chronotrace.capture.instrument import operation, reset_occurrences
from chronotrace.errors import InfeasibleOrderingError
from chronotrace.schedule.harness import ScheduleHarness, force_order

STORE: dict[str, str] = {}


@operation("write_op", resource="s.v", access="write")
async def write_op() -> None:
    STORE["v"] = "written"


@operation("read_op", resource="s.v", access="read")
async def read_op() -> str | None:
    return STORE.get("v")


async def _race() -> str | None:
    STORE.clear()
    task = asyncio.create_task(_delayed_write())
    observed = await read_op()
    await task
    return observed


async def _delayed_write() -> None:
    await asyncio.sleep(0)
    await write_op()


async def test_forcing_read_first_makes_the_read_stale():
    harness = ScheduleHarness(["read_op#0", "write_op#0"], timeout_s=2.0)
    with force_order(harness):
        assert await _race() is None
    assert harness.reached == ["read_op#0", "write_op#0"]


async def test_forcing_write_first_makes_the_read_fresh():
    harness = ScheduleHarness(["write_op#0", "read_op#0"], timeout_s=2.0)
    with force_order(harness):
        assert await _race() == "written"
    assert harness.reached == ["write_op#0", "read_op#0"]


async def test_both_orderings_are_reachable_from_the_same_code():
    """The point of the harness: one program, two outcomes, chosen by the harness."""
    reset_occurrences()
    first = ScheduleHarness(["read_op#0", "write_op#0"], timeout_s=2.0)
    with force_order(first):
        stale = await _race()
    reset_occurrences()
    second = ScheduleHarness(["write_op#0", "read_op#0"], timeout_s=2.0)
    with force_order(second):
        fresh = await _race()
    assert (stale, fresh) == (None, "written")


async def test_unreachable_ordering_is_infeasible_not_a_failure():
    """A gate that never opens means the candidate is unreachable (tier 1b)."""
    harness = ScheduleHarness(["never_runs#0", "read_op#0"], timeout_s=0.05)
    with force_order(harness), pytest.raises(InfeasibleOrderingError):
        await read_op()
    assert harness.infeasible is True
    assert harness.infeasible_op == "read_op#0"


async def test_operations_outside_the_forced_order_pass_through():
    harness = ScheduleHarness(["read_op#0"], timeout_s=1.0)
    with force_order(harness):
        await write_op()
        await read_op()
    assert harness.observed == ["write_op#0", "read_op#0"]
    assert harness.reached == ["read_op#0"]


async def test_harness_state_is_json_serializable():
    """Agent state must be primitive JSON (E4)."""
    import json

    harness = ScheduleHarness(["read_op#0"], timeout_s=1.0)
    with force_order(harness):
        await read_op()
    assert json.loads(json.dumps(harness.state()))["complete"] is True


async def test_no_harness_installed_is_a_no_op():
    STORE.clear()
    assert await read_op() is None
    await write_op()
    assert await read_op() == "written"


async def test_occurrence_indexes_distinguish_repeated_operations():
    """Spans are never keyed by name alone (D-3)."""
    reset_occurrences()
    harness = ScheduleHarness(["read_op#1"], timeout_s=1.0)
    with force_order(harness):
        await read_op()
        await read_op()
    assert harness.observed == ["read_op#0", "read_op#1"]
    assert harness.reached == ["read_op#1"]
