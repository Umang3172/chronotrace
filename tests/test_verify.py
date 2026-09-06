"""Verification behaviour: per-run counting, tier honesty, and the regression artifact."""

import json

from chronotrace.contracts import VerificationResult
from chronotrace.registry.loop_safety import LoopGuard
from chronotrace.verify.regression import append_regression_test, regression_test_name
from chronotrace.verify.runner import _read_report


def test_per_run_results_come_from_the_json_report_not_the_return_code(tmp_path):
    """V-1: a return code collapses 99-of-100-passing to a boolean."""
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "tests": [
                    {"outcome": "passed", "call": {"duration": 0.01}},
                    {"outcome": "failed", "call": {"duration": 0.02}},
                ]
            }
        )
    )
    passed, collected, duration = _read_report(report)
    assert (passed, collected) == (False, True)
    assert duration == 0.03


def test_absent_report_means_the_test_never_ran(tmp_path):
    """V3: infrastructure failure is not a test failure."""
    assert _read_report(tmp_path / "missing.json") == (False, False, 0.0)


def test_causal_proof_requires_both_halves():
    proven = VerificationResult(
        tier_reached="FORCED", pre_patch_forced_failed=True, post_patch_forced_passed=True
    )
    assert proven.causally_proven
    for partial in (
        VerificationResult(
            tier_reached="FORCED", pre_patch_forced_failed=False, post_patch_forced_passed=True
        ),
        VerificationResult(
            tier_reached="STATISTICAL",
            pre_patch_forced_failed=True,
            post_patch_forced_passed=True,
        ),
    ):
        assert not partial.causally_proven


def test_regression_guard_forces_the_order_and_keeps_fixtures_in_scope():
    source = (
        "import pytest\n\n\n@pytest.mark.asyncio\nasync def test_thing(session):\n    assert True\n"
    )
    guarded = append_regression_test(
        source,
        test_function="test_thing",
        forced_order=["r#0", "w#0"],
        incident_id="ab12cd34",
        natural_flake_rate=0.4,
    )
    assert regression_test_name("ab12cd34") in guarded
    assert "ScheduleHarness" in guarded
    assert "await test_thing(session)" in guarded
    assert "forced_order = ['r#0', 'w#0']" in guarded
    compile(guarded, "guard.py", "exec")


def test_loop_guard_stops_when_progress_stalls():
    guard = LoopGuard(max_rounds=5)
    assert guard.check(flake_rate=0.4, patch_set=["a"], deadlock=False).proceed
    verdict = guard.check(flake_rate=0.4, patch_set=["a", "b"], deadlock=False)
    assert not verdict.proceed
    assert "did not decrease" in verdict.reason


def test_loop_guard_detects_oscillation():
    guard = LoopGuard()
    guard.check(flake_rate=0.5, patch_set=["a"], deadlock=False)
    verdict = guard.check(flake_rate=0.2, patch_set=["a"], deadlock=False)
    assert not verdict.proceed
    assert "oscillation" in verdict.reason


def test_deadlock_halts_immediately():
    verdict = LoopGuard().check(flake_rate=0.1, patch_set=["a"], deadlock=True)
    assert not verdict.proceed
    assert "timed out" in verdict.reason


def test_round_cap_is_enforced():
    guard = LoopGuard(max_rounds=3)
    rates = [0.5, 0.4, 0.3]
    verdicts = [
        guard.check(flake_rate=rate, patch_set=[f"p{index}"], deadlock=False)
        for index, rate in enumerate(rates)
    ]
    assert [verdict.proceed for verdict in verdicts] == [True, True, False]
    assert "3-round cap" in verdicts[-1].reason
