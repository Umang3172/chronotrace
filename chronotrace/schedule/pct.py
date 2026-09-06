"""PCT — priority-based randomized scheduling (Tier 2).

Burckhardt et al., ASPLOS 2010. With ``n`` concurrent tasks and ``k`` scheduling
steps, PCT finds a bug of depth ``d`` with probability at least
``1 / (n * k**(d-1))`` per run. That converts "it passed N times" into a bound
on what could have been missed, which is the only defensible statistical claim
available here.

Tier 2 is a *probabilistic* bound and is never reported as causal proof (§21.4).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Sequence

__all__ = ["PCTPolicy", "detection_bound"]


class PCTPolicy:
    """A ready-queue policy implementing PCT's priority scheme.

    Each callback batch is ordered by a per-task priority. ``depth - 1`` change
    points lower a task's priority partway through the run, which is what lets
    the scheduler expose bugs that need more than one ordering constraint.

    Args:
        seed: Seed for the priority assignment, so a run is replayable.
        depth: Target bug depth ``d``.
        steps: Expected number of scheduling steps ``k``, used to place change points.

    """

    def __init__(self, seed: int, depth: int = 1, steps: int = 200) -> None:
        """Build a PCT policy for one run."""
        self.rng = random.Random(seed)
        self.depth = max(1, depth)
        self.steps = max(1, steps)
        self.step = 0
        self._priorities: dict[int, float] = {}
        self._change_points = sorted(self.rng.randrange(self.steps) for _ in range(self.depth - 1))

    def _priority(self, handle: asyncio.Handle) -> float:
        key = id(handle)
        if key not in self._priorities:
            self._priorities[key] = self.rng.random()
        return float(self._priorities[key])

    def __call__(self, ready: Sequence[asyncio.Handle]) -> list[asyncio.Handle]:
        """Order one batch of ready callbacks by priority, applying change points."""
        self.step += 1
        ordered = sorted(ready, key=self._priority)
        if self.step in self._change_points and ordered:
            demoted = ordered[0]
            self._priorities[id(demoted)] = 1.0 + self.rng.random()
            ordered = [*ordered[1:], demoted]
        return ordered


def detection_bound(tasks: int, steps: int, depth: int, runs: int) -> float:
    """Return the probability of having detected a depth-``depth`` bug in ``runs`` runs.

    Args:
        tasks: Number of concurrent tasks ``n``.
        steps: Number of scheduling steps ``k``.
        depth: Bug depth ``d``.
        runs: Independent PCT runs performed.

    Returns:
        ``1 - (1 - p)**runs`` where ``p = 1 / (n * k**(d-1))``.

    """
    if tasks <= 0 or steps <= 0 or runs <= 0:
        return 0.0
    per_run = 1.0 / float(tasks * steps ** max(0, depth - 1))
    return float(1.0 - (1.0 - per_run) ** runs)
