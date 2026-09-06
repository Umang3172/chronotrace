"""Loop safety: the mechanisms that stop the system chasing its own tail (spec 9.4).

The single most likely failure mode of a repair agent is infinite regress —
fixing A unmasks B, fixing B unmasks C, and nothing converges. Five guards, all
decidable:

* a hard cap on repair rounds (INV-8);
* monotone progress — the flake rate must strictly decrease each round;
* an accumulating regression suite, so round N re-verifies rounds 1..N-1 (INV-9);
* patch-set hashing, so returning to a previous state is detected as oscillation;
* a deadlock trip — any timeout rolls back and halts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

__all__ = ["LoopGuard", "LoopVerdict"]


@dataclass(frozen=True)
class LoopVerdict:
    """Whether another repair round may start, and why not when it may not."""

    proceed: bool
    reason: str = ""


@dataclass
class LoopGuard:
    """Tracks repair rounds for one test and decides when to stop."""

    max_rounds: int = 5
    rounds: int = 0
    flake_rates: list[float] = field(default_factory=list)
    patch_hashes: list[str] = field(default_factory=list)
    guards: list[str] = field(default_factory=list)
    """Regression guards accumulated so far; every round re-verifies all of them."""

    def check(self, *, flake_rate: float, patch_set: list[str], deadlock: bool) -> LoopVerdict:
        """Decide whether another round is allowed after the round just finished.

        Args:
            flake_rate: Flake rate measured at the end of this round.
            patch_set: Diffs applied so far, hashed to detect oscillation.
            deadlock: Whether a verification run timed out this round.

        Returns:
            The verdict, carrying a plain-language reason when stopping.

        """
        self.rounds += 1
        digest = hashlib.sha256("".join(sorted(patch_set)).encode()).hexdigest()[:16]
        if deadlock:
            return LoopVerdict(False, "a verification run timed out: rolled back and halted")
        if digest in self.patch_hashes:
            return LoopVerdict(
                False, "the patch set returned to a previous state, which is oscillation"
            )
        self.patch_hashes.append(digest)
        if self.flake_rates and flake_rate >= self.flake_rates[-1]:
            self.flake_rates.append(flake_rate)
            return LoopVerdict(
                False,
                f"flake rate did not decrease ({self.flake_rates[-2]:.0%} -> {flake_rate:.0%}); "
                "no progress is being made",
            )
        self.flake_rates.append(flake_rate)
        if flake_rate <= 0.0:
            return LoopVerdict(False, "no residual flakiness remains")
        if self.rounds >= self.max_rounds:
            return LoopVerdict(False, f"reached the {self.max_rounds}-round cap")
        return LoopVerdict(True)

    def add_guard(self, guard_test_id: str) -> None:
        """Record a regression guard that every later round must keep green (INV-9)."""
        if guard_test_id not in self.guards:
            self.guards.append(guard_test_id)
