"""Ready-queue control — the secondary forcing mechanism (§21.3).

Harness gates cover orderings expressible at instrumented operation entry. When
the ordering lives inside library code that cannot be wrapped, the remaining
control point is the event loop's ready queue.

``loop._ready`` is private API. It is asserted at construction and the loop
fails loudly if a future CPython removes it, because silently degrading to an
unordered loop while still reporting FORCED would make the whole claim
dishonest.
"""

from __future__ import annotations

import asyncio
import collections
import selectors
from collections.abc import Callable, Sequence
from typing import Any

from chronotrace.errors import UnsupportedRuntimeError

ReadyPolicy = Callable[[Sequence[Any]], list[Any]]

__all__ = [
    "DeterministicLoop",
    "DeterministicLoopPolicy",
    "assert_supported",
    "loop_factory",
]


def assert_supported() -> None:
    """Fail loudly if the interpreter does not expose the loop internals we need."""
    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    try:
        if not hasattr(loop, "_ready") or not isinstance(loop._ready, collections.deque):
            raise UnsupportedRuntimeError(
                "asyncio loop does not expose a '_ready' deque; the deterministic loop "
                "cannot be installed on this interpreter. Pin Python 3.11-3.13 or use "
                "harness gates only (§21.2)."
            )
    finally:
        loop.close()


class DeterministicLoop(asyncio.SelectorEventLoop):
    """An event loop that reorders each batch of ready callbacks by an explicit policy."""

    def __init__(self, policy: ReadyPolicy, *args: Any, **kwargs: Any) -> None:
        """Build a loop that applies ``policy`` to every ready batch."""
        super().__init__(*args, **kwargs)
        assert_supported()
        self._policy = policy
        self.steps = 0

    def _run_once(self) -> None:
        # ``_ready`` and ``_run_once`` are private asyncio API. That is the whole
        # point of this class, and it is why assert_supported() runs first and
        # fails loudly rather than degrading to an unordered loop.
        ready = self._ready  # type: ignore[has-type]
        if ready:
            self.steps += 1
            self._ready = collections.deque(self._policy(list(ready)))
        super()._run_once()  # type: ignore[misc]


def loop_factory(policy: ReadyPolicy) -> Callable[[], asyncio.AbstractEventLoop]:
    """Return a ``loop_factory`` installing a :class:`DeterministicLoop` with ``policy``."""

    def factory() -> asyncio.AbstractEventLoop:
        return DeterministicLoop(policy, selectors.SelectSelector())

    return factory


class DeterministicLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy handing out :class:`DeterministicLoop` instances.

    Installed by the capture plugin for Tier 2 runs, so the scheduling policy
    reaches loops that pytest-asyncio creates rather than only loops we build
    ourselves.
    """

    def __init__(self, policy_factory: Callable[[], ReadyPolicy]) -> None:
        """Store the factory producing a fresh policy per loop."""
        super().__init__()
        self._policy_factory = policy_factory

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        """Return a deterministic loop driven by a fresh policy."""
        return DeterministicLoop(self._policy_factory(), selectors.SelectSelector())
