"""N01 random_seed_flake: a negative control. The nondeterminism is in the data.

ChronoTrace must refuse this. Every run produces the same operation ordering;
what varies is a value drawn from an unseeded generator. There is no
interleaving to invert, so there is nothing for a synchronization primitive to
fix.
"""

import random

import pytest

from chronotrace.capture.instrument import assertion, operation

SAMPLES: list[float] = []


@operation("draw_sample", resource="rng.sample", access="write")
async def draw_sample() -> float:
    """Draw a sample from an unseeded generator."""
    value = random.random()  # noqa: S311
    SAMPLES.append(value)
    return value


@operation("read_sample", resource="rng.sample", access="read")
async def read_sample() -> float:
    """Read back the most recent sample."""
    return SAMPLES[-1]


@pytest.mark.asyncio
async def test_sample_is_above_threshold() -> None:
    SAMPLES.clear()
    await draw_sample()
    value = await read_sample()
    with assertion("rng.sample"):
        assert value > 0.15
