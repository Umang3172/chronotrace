"""The verification ladder, and the honesty rule attached to it (spec 21.4).

```
TIER 1  FORCED      the ordering was reproduced           -> causality PROVEN
TIER 1b INFEASIBLE  the ordering could not be reached     -> candidate discarded
TIER 2  PCT         seeded randomized scheduling, N runs  -> probabilistic bound
TIER 3  STATISTICAL plain reruns, N/N stable              -> residual check only
```

**A Tier 2 or Tier 3 result is never reported as causal proof.** Silently
degrading and still claiming proof is the one thing that would make this project
dishonest, so the tier reached is carried in the result and rendered everywhere
the result is.

Seeds are pinned for Tier 1 and left alone for Tier 3. Pinning them for the
residual check would make "N/N stable" true by construction.
"""

from __future__ import annotations

import contextlib
import statistics
from collections.abc import Iterator
from pathlib import Path

from chronotrace.contracts import VerificationResult
from chronotrace.logging import get_logger
from chronotrace.schedule import determinism
from chronotrace.schedule.pct import detection_bound
from chronotrace.verify.runner import run_test

log = get_logger(__name__)

__all__ = ["patched_file", "verify"]

FORCED_SEED = 1729


@contextlib.contextmanager
def patched_file(path: Path, patched: str) -> Iterator[None]:
    """Write ``patched`` to ``path`` for the duration of the block, then restore it."""
    original = path.read_text()
    path.write_text(patched)
    try:
        yield
    finally:
        path.write_text(original)


def verify(
    *,
    test_id: str,
    cwd: Path,
    target: Path,
    patched_source: str,
    forced_order: list[str],
    timeout_s: float = 30.0,
    gate_timeout_s: float = 5.0,
    forced_runs: int = 5,
    statistical_runs: int = 20,
    pct_runs: int = 0,
    isolation: str = "process",
) -> VerificationResult:
    """Verify a patch across the tiers, reporting the tier actually reached.

    Args:
        test_id: The test under repair.
        cwd: Repository root.
        target: File the patch modifies.
        patched_source: The patched contents of ``target``.
        forced_order: Operation keys reproducing the race.
        timeout_s: Per-run wall-clock cap; a breach is a deadlock signal.
        gate_timeout_s: Cap on one forced-ordering gate.
        forced_runs: Runs per forced-ordering phase.
        statistical_runs: Tier 3 sample size.
        pct_runs: Tier 2 sample size. Zero means PCT was not attempted, which is
            reported as such rather than as a pass.
        isolation: ``"process"`` or ``"docker"``.

    Returns:
        The verification result, including measured overhead and the
        reproduction seed.

    """
    force = {"test_id": test_id, "order": forced_order, "gate_timeout_s": gate_timeout_s}
    # Forced runs sweep consecutive seeds rather than repeating one. The harness
    # constrains the pair under test; leaving the rest of the schedule free is
    # what keeps "passes under the forced ordering" from meaning "passes under
    # one particular schedule".
    result = VerificationResult(
        tier_reached="FAILED",
        isolation=isolation,  # type: ignore[arg-type]
        reproduction_seed=determinism.reproduction_seed(FORCED_SEED, forced_order, forced_runs),
    )

    pre_natural_failures, pre_natural_durations = _natural_phase(
        test_id, cwd, statistical_runs, timeout_s, isolation
    )
    pre_failures, _pre_durations, pre_state = _forced_phase(
        test_id, cwd, force, forced_runs, timeout_s, isolation
    )
    if pre_state == "TIMEOUT":
        result.deadlock_detected = True
        return result
    if pre_state == "INFEASIBLE":
        result.tier_reached = "INFEASIBLE"
        return result
    result.pre_patch_forced_failed = pre_failures == forced_runs

    with patched_file(target, patched_source):
        post_failures, _post_durations, post_state = _forced_phase(
            test_id, cwd, force, forced_runs, timeout_s, isolation
        )
        if post_state == "TIMEOUT":
            result.deadlock_detected = True
            result.tier_reached = "FAILED"
            return result
        if post_state == "INFEASIBLE":
            # The repair made the ordering unreachable rather than harmless.
            # That is a real outcome, but it is not the proof we claim.
            result.tier_reached = "INFEASIBLE"
            return result
        result.post_patch_forced_passed = post_failures == 0

        natural_failures, natural_durations = _natural_phase(
            test_id, cwd, statistical_runs, timeout_s, isolation
        )
        result.statistical_runs = statistical_runs
        result.statistical_failures = natural_failures
        result.pre_patch_natural_failures = pre_natural_failures

        if pct_runs > 0:
            result.pct_runs = pct_runs
            result.pct_failures = _pct_phase(test_id, cwd, pct_runs, timeout_s, isolation)

    result.measured_overhead_ms = _overhead_ms(pre_natural_durations, natural_durations)

    if result.pre_patch_forced_failed and result.post_patch_forced_passed:
        result.tier_reached = "FORCED"
    elif result.pct_runs and result.pct_failures == 0:
        result.tier_reached = "PCT"
    elif result.statistical_failures == 0:
        result.tier_reached = "STATISTICAL"
    else:
        result.tier_reached = "FAILED"

    result.symptom_patch_suspected = (
        result.tier_reached == "FORCED" and result.statistical_failures > 0
    )
    if result.symptom_patch_suspected:
        log.warning(
            "verify.symptom_suspected",
            test_id=test_id,
            residual_failures=result.statistical_failures,
        )
    return result


def _forced_phase(
    test_id: str,
    cwd: Path,
    force: dict[str, object],
    runs: int,
    timeout_s: float,
    isolation: str,
) -> tuple[int, list[float], str]:
    failures = 0
    durations: list[float] = []
    for run_index in range(runs):
        outcome = run_test(
            test_id,
            cwd=cwd,
            timeout_s=timeout_s,
            force=force,
            seed=FORCED_SEED + run_index,
            hash_seed="0",
            isolation=isolation,
        )
        if outcome.timed_out:
            return failures, durations, "TIMEOUT"
        if outcome.infeasible:
            return failures, durations, "INFEASIBLE"
        durations.append(outcome.test_duration_s)
        if not outcome.passed:
            failures += 1
    return failures, durations, "OK"


def _natural_phase(
    test_id: str, cwd: Path, runs: int, timeout_s: float, isolation: str
) -> tuple[int, list[float]]:
    failures = 0
    durations: list[float] = []
    for _ in range(runs):
        outcome = run_test(test_id, cwd=cwd, timeout_s=timeout_s, seed=None, isolation=isolation)
        if outcome.timed_out:
            failures += 1
            continue
        durations.append(outcome.test_duration_s)
        if not outcome.passed:
            failures += 1
    return failures, durations


def _pct_phase(test_id: str, cwd: Path, runs: int, timeout_s: float, isolation: str) -> int:
    failures = 0
    for index in range(runs):
        outcome = run_test(
            test_id,
            cwd=cwd,
            timeout_s=timeout_s,
            seed=FORCED_SEED + index,
            pct_seed=FORCED_SEED + index,
            isolation=isolation,
        )
        if outcome.timed_out or not outcome.passed:
            failures += 1
    return failures


def _overhead_ms(before: list[float], after: list[float]) -> float:
    """Measured runtime delta in milliseconds (spec 19.3).

    Median test-call duration under natural conditions, before the patch versus
    after it. Never claimed as zero: a synchronization primitive changes
    scheduling and contention even when it introduces no fixed delay. The
    defensible claim is "no fixed sleep-based delay introduced", plus this
    number.
    """
    if not before or not after:
        return 0.0
    return round((statistics.median(after) - statistics.median(before)) * 1000, 3)


def pct_confidence(tasks: int, steps: int, depth: int, runs: int) -> float:
    """Re-export the PCT detection bound for reporting alongside a Tier 2 result."""
    return detection_bound(tasks, steps, depth, runs)
