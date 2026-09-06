"""Confirm candidates by forcing them (spec 9.1 stage 3, spec 13).

Ranking produces a suspicion. Forcing produces a decision:

* forced failure rate 1.0 — the ordering is a sufficient condition for failure,
  so the candidate is **causally sufficient**. Proven, not inferred.
* forced failure rate 0.0 — noise. Discard.
* strictly between — necessary but not sufficient. The bug needs more than one
  scheduling constraint, which is bug *depth* in the PCT sense. ChronoTrace
  implements depth 1 properly and reports depth >= 2 rather than patching a
  symptom.
* the ordering could not be reached at all — INFEASIBLE, a diagnostic result
  rather than a failure.
"""

from __future__ import annotations

from pathlib import Path

from chronotrace.contracts import CandidateInversion
from chronotrace.logging import get_logger
from chronotrace.verify.runner import run_test

log = get_logger(__name__)

__all__ = ["ConfirmationBudget", "confirm"]

DEFAULT_SEED = 1729


class ConfirmationBudget:
    """How much forcing the diagnosis stage is allowed to spend."""

    def __init__(self, candidates: int = 5, runs: int = 5) -> None:
        """Set the candidate and per-candidate run limits."""
        self.candidates = candidates
        self.runs = runs


def confirm(
    candidates: list[CandidateInversion],
    *,
    test_id: str,
    cwd: Path,
    budget: ConfirmationBudget | None = None,
    timeout_s: float = 30.0,
    gate_timeout_s: float = 5.0,
    seed: int = DEFAULT_SEED,
) -> tuple[list[CandidateInversion], bool]:
    """Force each candidate ordering in turn and classify it by what happens.

    Args:
        candidates: Ranked candidates, best first.
        test_id: The test to run.
        cwd: Repository root.
        budget: Candidate and run limits.
        timeout_s: Per-run wall-clock cap.
        gate_timeout_s: Cap on a single gate wait before an ordering is
            declared unreachable.
        seed: Base determinism seed. Runs sweep ``seed, seed+1, ...`` rather
            than repeating one seed: forcing constrains the candidate ordering,
            and everything *not* forced has to stay free or a bug that needs two
            constraints would read as a single sufficient one.

    Returns:
        ``(classified_candidates, deadlock_detected)``. Classification stops at
        the first causally sufficient candidate; the rest stay ``UNTESTED``.

    """
    budget = budget or ConfirmationBudget()
    deadlock = False
    for index, candidate in enumerate(candidates):
        if index >= budget.candidates:
            break
        force = {
            "test_id": test_id,
            "order": candidate.failing_order,
            "gate_timeout_s": gate_timeout_s,
        }
        failures = 0
        executed = 0
        infeasible = False
        for run_index in range(budget.runs):
            outcome = run_test(
                test_id,
                cwd=cwd,
                timeout_s=timeout_s,
                force=force,
                seed=seed + run_index,
                hash_seed="0",
            )
            if outcome.timed_out:
                deadlock = True
                log.warning("confirm.timeout", test_id=test_id, order=candidate.failing_order)
                break
            if outcome.infeasible:
                infeasible = True
                break
            executed += 1
            if not outcome.passed:
                failures += 1
        if infeasible:
            candidate.classification = "INFEASIBLE"
            candidate.forced_failure_rate = None
            continue
        if executed == 0:
            continue
        rate = failures / executed
        candidate.forced_failure_rate = rate
        if rate >= 1.0:
            candidate.classification = "CAUSALLY_SUFFICIENT"
            log.info("confirm.sufficient", order=candidate.failing_order)
            break
        if rate <= 0.0:
            candidate.classification = "IRRELEVANT"
        else:
            candidate.classification = "NECESSARY_INSUFFICIENT"
            log.info("confirm.insufficient", order=candidate.failing_order, rate=round(rate, 3))
    return candidates, deadlock
