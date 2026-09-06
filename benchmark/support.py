"""Shared helpers for the seeded benchmark corpus.

Read this before reading a case: it explains where the nondeterminism in these
tests comes from.

asyncio task scheduling is deterministic for a fixed program, so a race seeded
into pure asyncio code would fail 0% or 100% of the time and would not be a
flaky test at all. Real async flakiness comes from I/O completion times varying
between runs. :func:`io_latency` models exactly that, and it is the *only*
source of nondeterminism in the repairable cases.

That jitter sits **outside** every instrumented operation. The operation bodies
are the state accesses themselves, so the order in which operations start is
what decides the outcome — which is the property the forced-ordering harness
acts on.
"""

from __future__ import annotations

import asyncio
import random

MAX_JITTER_S = 0.0015


async def io_latency(scale: float = 1.0) -> None:
    """Model variable I/O completion time.

    This is a benchmark fixture, not a repair. ChronoTrace patches are forbidden
    from containing anything of this shape (governor rule N1).
    """
    await asyncio.sleep(random.uniform(0.0, MAX_JITTER_S) * scale)
