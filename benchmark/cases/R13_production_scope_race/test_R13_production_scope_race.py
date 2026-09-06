"""R13 production_scope_race: the race lives in application code, not the test."""

import asyncio

import pytest

from benchmark.cases.R13_production_scope_race.app_service import (
    CACHE,
    serve_config,
    warm_cache,
)
from benchmark.support import io_latency
from chronotrace.capture.instrument import assertion


@pytest.mark.asyncio
async def test_service_serves_warm_config() -> None:
    CACHE.clear()
    task = asyncio.create_task(warm_cache())
    await io_latency()
    value = await serve_config()
    with assertion("cache.entry"):
        assert value == "v1"
    await task
