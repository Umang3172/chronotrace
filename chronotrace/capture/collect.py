"""Trace-pair collection (E1, D3).

Diagnosis compares a passing execution against a failing one. Getting both for a
1-in-20 flake takes runs, and the honest failure mode when they do not appear is
to say so: a diagnosis derived from a single trace is not a diagnosis.

This stage also measures the probe effect (D3) by running the same test with
instrumentation off. Instrumentation changes timing; publishing the delta is
credibility, hiding it is not.
"""

from __future__ import annotations

from pathlib import Path

from chronotrace.capture.fingerprint import comparable
from chronotrace.contracts import CaptureBundle
from chronotrace.logging import get_logger
from chronotrace.verify.runner import run_test

log = get_logger(__name__)

__all__ = ["collect"]


def collect(
    test_id: str,
    *,
    cwd: Path,
    runs: int = 30,
    timeout_s: float = 30.0,
    min_pass: int = 1,
    min_fail: int = 1,
    probe_runs: int = 0,
) -> CaptureBundle:
    """Run ``test_id`` until a comparable pass/fail pair exists or the budget runs out.

    Args:
        test_id: pytest node id of the flaky test.
        cwd: Repository root.
        runs: Maximum instrumented runs to spend.
        timeout_s: Per-run wall-clock cap.
        min_pass: Passing traces required before stopping early.
        min_fail: Failing traces required before stopping early.
        probe_runs: Uninstrumented runs used to measure the probe effect (D3).

    Returns:
        The bundle of captured traces and the rates measured while capturing.

    """
    bundle = CaptureBundle(test_id=test_id)
    reference = None
    failures = 0
    for index in range(runs):
        outcome = run_test(
            test_id, cwd=cwd, timeout_s=timeout_s, capture=True, seed=None, hash_seed="0"
        )
        bundle.runs_executed += 1
        if outcome.timed_out:
            bundle.runs_timed_out += 1
            log.warning("capture.timeout", test_id=test_id, run=index)
            continue
        capture = outcome.capture
        if capture is None:
            log.warning("capture.no_spans", test_id=test_id, run=index, passed=outcome.passed)
            if not outcome.passed:
                failures += 1
            continue
        if reference is None:
            reference = capture.fingerprint
        elif not comparable(reference, capture.fingerprint):
            bundle.fingerprint_conflicts += 1
            log.warning("capture.fingerprint_mismatch", test_id=test_id, run=index)
            continue
        if capture.outcome == "PASS":
            bundle.passing.append(capture)
        else:
            bundle.failing.append(capture)
            failures += 1
        if len(bundle.passing) >= min_pass and len(bundle.failing) >= min_fail and index >= 9:
            break
    executed = max(1, bundle.runs_executed - bundle.runs_timed_out)
    bundle.natural_flake_rate = failures / executed
    if probe_runs > 0:
        bundle.uninstrumented_flake_rate = _uninstrumented_rate(
            test_id, cwd=cwd, runs=probe_runs, timeout_s=timeout_s
        )
    log.info(
        "capture.done",
        test_id=test_id,
        passing=len(bundle.passing),
        failing=len(bundle.failing),
        flake_rate=round(bundle.natural_flake_rate, 3),
    )
    return bundle


def _uninstrumented_rate(test_id: str, *, cwd: Path, runs: int, timeout_s: float) -> float:
    failures = 0
    executed = 0
    for _ in range(runs):
        outcome = run_test(test_id, cwd=cwd, timeout_s=timeout_s, capture=False, seed=None)
        if outcome.timed_out:
            continue
        executed += 1
        if not outcome.passed:
            failures += 1
    return failures / max(1, executed)
