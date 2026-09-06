"""Forced-ordering harness — the control point the whole method rests on (§21.2).

asyncio is tractable because tasks yield only at ``await`` boundaries and the
loop picks the next ready callback. That choice is the control point, so this
harness does not fight an OS scheduler; it gates *when instrumented operations
start*.

The gate opens for an operation as soon as its predecessor has **started**, not
finished. That distinction is what makes the experiment sound:

* pre-patch, forcing ``read`` before ``write`` lets ``read`` observe stale state
  and the assertion fails;
* post-patch, ``read`` starts, blocks on the injected primitive, ``write`` is
  released, and the test passes.

The harness is identical in both runs, so the only variable is the patch. It is
installed by the verifier for the duration of a run and removed afterwards; it
is never written into a patch and never ships in the repository under test
(INV-1 keeps patches to synchronization primitives only).
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from chronotrace.errors import InfeasibleOrderingError

__all__ = ["ScheduleHarness", "active_harness", "checkpoint", "force_order", "patch_targets"]


class ScheduleHarness:
    """Forces a specific start-order between instrumented operations.

    Args:
        order: Operation keys (``"name#occurrence"``) in the order to force.
        timeout_s: Cap on a single gate wait. A breach means the ordering cannot
            be produced by this code, which is a diagnostic result (Tier 1b
            INFEASIBLE), not a test failure.

    """

    def __init__(self, order: list[str], timeout_s: float = 5.0) -> None:
        """Build the gates for ``order``."""
        self.order = list(order)
        self.timeout_s = timeout_s
        self.gates: dict[str, asyncio.Event] = {op: asyncio.Event() for op in self.order}
        self.reached: list[str] = []
        self.observed: list[str] = []
        self.infeasible = False
        self.infeasible_op: str | None = None

    async def checkpoint(self, op_id: str) -> None:
        """Gate entry to ``op_id``. Called at the start of each instrumented operation.

        Operations outside the forced order are recorded and pass through
        untouched — the harness constrains the pair under test, not the program.

        Raises:
            InfeasibleOrderingError: The predecessor never started within
                ``timeout_s``, so this ordering is unreachable.

        """
        self.observed.append(op_id)
        if op_id not in self.gates:
            return
        idx = self.order.index(op_id)
        if idx > 0:
            predecessor = self.order[idx - 1]
            try:
                await asyncio.wait_for(self.gates[predecessor].wait(), timeout=self.timeout_s)
            except TimeoutError as exc:
                self.infeasible = True
                self.infeasible_op = op_id
                raise InfeasibleOrderingError(
                    f"forced ordering unreachable: {op_id} waited "
                    f"{self.timeout_s}s for {predecessor}"
                ) from exc
        self.reached.append(op_id)
        self.gates[op_id].set()

    def state(self) -> dict[str, Any]:
        """JSON-serializable harness state for the verifier to read back (E4)."""
        return {
            "order": self.order,
            "reached": self.reached,
            "observed": self.observed,
            "infeasible": self.infeasible,
            "infeasible_op": self.infeasible_op,
            "complete": self.reached == self.order,
        }


_ACTIVE: ScheduleHarness | None = None


def active_harness() -> ScheduleHarness | None:
    """Return the harness installed for the current run, if any."""
    return _ACTIVE


async def checkpoint(op_id: str) -> None:
    """Gate ``op_id`` against the active harness; a no-op when none is installed."""
    harness = _ACTIVE
    if harness is not None:
        await harness.checkpoint(op_id)


@contextlib.contextmanager
def force_order(harness: ScheduleHarness | None) -> Iterator[ScheduleHarness | None]:
    """Install ``harness`` for the duration of the block, then remove it."""
    global _ACTIVE
    previous = _ACTIVE
    _ACTIVE = harness
    try:
        yield harness
    finally:
        _ACTIVE = previous


@contextlib.contextmanager
def patch_targets(harness: ScheduleHarness, targets: dict[str, str]) -> Iterator[None]:
    """Gate operations that carry no ChronoTrace instrumentation.

    The primary mechanism gates at instrumentation points. This secondary path
    wraps arbitrary coroutine functions in place, for code that predates
    instrumentation or lives behind a framework boundary.

    Args:
        harness: The harness whose gates the wrappers should hit.
        targets: Operation key -> dotted path of an async function, e.g.
            ``{"write#0": "app.store.write_value"}``.

    """
    originals: list[tuple[Any, str, Callable[..., Any]]] = []
    for op_id, dotted in sorted(targets.items()):
        module_path, _, attr = dotted.rpartition(".")
        module = importlib.import_module(module_path)
        original = getattr(module, attr)

        # ANN401: the wrapper stands in for an arbitrary user coroutine, so its
        # signature and return type are genuinely the wrapped function's.
        async def wrapped(
            *args: Any,
            _op: str = op_id,
            _fn: Any = original,  # noqa: ANN401
            **kwargs: Any,
        ) -> Any:  # noqa: ANN401
            await harness.checkpoint(_op)
            return await _fn(*args, **kwargs)

        setattr(module, attr, wrapped)
        originals.append((module, attr, original))
    try:
        yield
    finally:
        for module, attr, original in reversed(originals):
            setattr(module, attr, original)


@contextlib.asynccontextmanager
async def forced(order: list[str], timeout_s: float = 5.0) -> AsyncIterator[ScheduleHarness]:
    """Build a harness, install it, and yield it for the duration of the block."""
    harness = ScheduleHarness(order, timeout_s=timeout_s)
    with force_order(harness):
        yield harness
