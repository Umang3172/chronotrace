"""R03 taskgroup_teardown: the test asserts a side effect of a task it never awaited."""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

REPORT: dict[str, str] = {}


@operation("finalize_report", resource="report.status", access="write")
async def finalize_report() -> None:
    """Write the terminal status of the report."""
    REPORT["status"] = "done"


@operation("read_status", resource="report.status", access="read")
async def read_status() -> str | None:
    """Read the report status."""
    return REPORT.get("status")


async def worker() -> None:
    """Background worker finishing after a variable delay."""
    await io_latency()
    await finalize_report()


@pytest.mark.asyncio
async def test_report_is_finalized() -> None:
    REPORT.clear()
    handle = asyncio.create_task(worker())
    await io_latency()
    status = await read_status()
    with assertion("report.status"):
        assert status == "done"
    await handle
