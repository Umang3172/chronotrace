"""Determinism controls for replay (§21.5).

A forced ordering is only reproducible if everything else is pinned too. What is
pinned is recorded in the incident report as the reproduction seed, which is
part of the shipped artifact (§19.10) — a replay someone else cannot reproduce
is not evidence.

``PYTHONHASHSEED`` cannot be changed after interpreter start, so it is set in
the child process environment by the runner and only *reported* here.
"""

from __future__ import annotations

import os
import random
import sys
from typing import Any

__all__ = ["pin", "reproduction_seed"]


def pin(seed: int) -> dict[str, str]:
    """Pin every in-process source of nondeterminism this run can control.

    Args:
        seed: The seed to apply to ``random`` and, when installed, numpy.

    Returns:
        The reproduction seed: what was pinned, to what value.

    """
    random.seed(seed)
    pinned: dict[str, str] = {
        "random_seed": str(seed),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "unset"),
        "python_version": sys.version.split()[0],
        "tz": os.environ.get("TZ", "system"),
    }
    numpy: Any = sys.modules.get("numpy")
    if numpy is not None:
        numpy.random.seed(seed)
        pinned["numpy_seed"] = str(seed)
    return pinned


def reproduction_seed(seed: int, order: list[str], runs: int = 1) -> dict[str, str]:
    """Describe how to reproduce a forced replay exactly.

    Args:
        seed: Base seed. Runs sweep ``seed`` upwards, one per run.
        order: The forced operation ordering.
        runs: How many runs the sweep covered.

    """
    pinned = {
        "random_seed_base": str(seed),
        "random_seed_sweep": f"{seed}..{seed + max(0, runs - 1)}",
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "0"),
        "python_version": sys.version.split()[0],
        "forced_order": " -> ".join(order),
    }
    return pinned
