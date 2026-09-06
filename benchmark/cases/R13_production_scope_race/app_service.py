"""Application code for R13. This is product code, not test code.

A race here is a production defect. Patching it to make a test green would hide
a real bug, which is the single worst outcome in the register (D8 / INV-7).
"""

from benchmark.support import io_latency
from chronotrace.capture.instrument import operation

CACHE: dict[str, str] = {}


@operation("cache_fill", resource="cache.entry", access="write")
async def cache_fill(key: str, value: str) -> None:
    """Populate the cache entry."""
    CACHE[key] = value


@operation("cache_get", resource="cache.entry", access="read")
async def cache_get(key: str) -> str | None:
    """Read the cache entry, falling back to None on a miss."""
    return CACHE.get(key)


async def warm_cache() -> None:
    """Warm the cache in the background at service start."""
    await io_latency()
    await cache_fill("config", "v1")


async def serve_config() -> str | None:
    """Serve the config value, which the service assumes is warm by now."""
    return await cache_get("config")
