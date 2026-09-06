"""R02 commit_before_select: a read query races the transaction that commits its row."""

import asyncio

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation

ROWS: list[dict[str, str]] = []


@operation("db_commit", resource="db.rows", access="write")
async def db_commit(row: dict[str, str]) -> None:
    """Commit a row into the table."""
    ROWS.append(row)


@operation("db_select", resource="db.rows", access="read")
async def db_select(key: str) -> dict[str, str] | None:
    """Select the row with ``key``."""
    return next((row for row in ROWS if row["id"] == key), None)


async def transaction() -> None:
    """A transaction that commits after some round-trip latency."""
    await io_latency()
    await db_commit({"id": "u1", "email": "u1@example.com"})


@pytest.mark.asyncio
async def test_select_sees_committed_row() -> None:
    ROWS.clear()
    tx = asyncio.create_task(transaction())
    await io_latency()
    row = await db_select("u1")
    with assertion("db.rows"):
        assert row is not None
    await tx
