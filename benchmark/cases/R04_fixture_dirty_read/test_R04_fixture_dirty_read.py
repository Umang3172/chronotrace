"""R04 fixture_dirty_read: a background task mutates a shared fixture mid-test."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion, operation


class Session:
    """A session object shared by the test and a background refresher."""

    def __init__(self) -> None:
        self.token: str | None = None


@operation("refresh_token", resource="session.token", access="write")
async def refresh_token(session: Session) -> None:
    """Install a fresh token on the session."""
    session.token = "tok-2"


@operation("use_token", resource="session.token", access="read")
async def use_token(session: Session) -> str | None:
    """Read the token the request will be signed with."""
    return session.token


async def refresher(session: Session) -> None:
    """Refresh the token once the upstream call returns."""
    await io_latency()
    await refresh_token(session)


@pytest.fixture
async def session() -> AsyncIterator[Session]:
    """Provide a fresh session per test."""
    yield Session()


@pytest.mark.asyncio
async def test_request_uses_refreshed_token(session: Session) -> None:
    task = asyncio.create_task(refresher(session))
    await io_latency()
    token = await use_token(session)
    with assertion("session.token"):
        assert token == "tok-2"
    await task
