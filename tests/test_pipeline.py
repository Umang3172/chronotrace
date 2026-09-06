"""End-to-end behaviour against the seeded corpus.

These run the real pipeline over a real flaky test, so they are slower than the
rest of the suite and marked accordingly.
"""

from pathlib import Path

import pytest

from chronotrace.config import Settings
from chronotrace.eval.cases import load_cases
from chronotrace.pipeline import repair
from chronotrace.providers.local import LocalModelProvider

ROOT = Path(__file__).resolve().parents[1]
CASES = {case.case_id: case for case in load_cases(ROOT / "benchmark" / "cases")}


def _run(case_id: str, **overrides):
    settings = Settings(statistical_runs=6, **overrides)
    return repair(
        CASES[case_id].test_id,
        cwd=ROOT,
        provider=LocalModelProvider(),
        settings=settings,
        capture_runs=14,
    )


@pytest.mark.benchmark
def test_race_is_proven_patched_and_verified():
    report = _run("R01")
    assert report.ui_state == "FIXED"
    assert report.diagnosis.status == "RACE_PROVEN"
    assert report.verification.causally_proven
    assert report.verification.pre_patch_forced_failed is True
    assert report.verification.post_patch_forced_passed is True
    assert report.regression_verified
    assert report.intent.transformation == "INJECT_ASYNC_EVENT"


@pytest.mark.benchmark
def test_the_repo_is_not_modified_unless_asked():
    """ChronoTrace proposes a diff; a human merges."""
    target = ROOT / CASES["R01"].test_id.split("::")[0]
    before = target.read_text()
    report = _run("R01")
    assert report.unified_diff
    assert target.read_text() == before


@pytest.mark.benchmark
def test_threading_case_abstains():
    report = _run("N07")
    assert report.ui_state == "ABSTAINED"
    assert report.diagnosis.abstain_reason == "NON_ASYNCIO_PARADIGM"
    assert report.unified_diff is None


@pytest.mark.benchmark
def test_production_scope_race_abstains_without_opt_in():
    report = _run("R13")
    assert report.ui_state == "ABSTAINED"
    assert report.diagnosis.abstain_reason == "PRODUCTION_SCOPE_RACE"
    assert report.diagnosis.proven_inversion is not None
