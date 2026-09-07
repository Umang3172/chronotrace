"""Unit coverage for the pieces the end-to-end tests exercise only incidentally."""

import asyncio
import json

import pytest

from chronotrace.capture.instrument import operation, reset_occurrences
from chronotrace.contracts import Diagnosis, IncidentReport, OperationRef
from chronotrace.errors import ProviderError
from chronotrace.eval.cases import load_cases
from chronotrace.eval.report import render_markdown, summarise
from chronotrace.eval.score import _contains_band_aid, score_arm
from chronotrace.providers.reference_policy import ReferencePolicyProvider
from chronotrace.registry.store import IncidentStore
from chronotrace.schedule import determinism
from chronotrace.schedule.harness import ScheduleHarness, patch_targets
from chronotrace.schedule.loop import DeterministicLoop, assert_supported, loop_factory
from chronotrace.schedule.pct import PCTPolicy, detection_bound

# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #


def _report(incident_id="i1", state="FIXED"):
    return IncidentReport(
        incident_id=incident_id,
        test_id="t.py::test_x",
        ui_state=state,
        diagnosis=Diagnosis(status="RACE_PROVEN"),
    )


def test_store_round_trips_and_exports(tmp_path):
    store = IncidentStore(tmp_path / "db.sqlite3")
    store.save(_report("a"))
    store.save(_report("b", "ABSTAINED"))
    assert store.get("a").incident_id == "a"
    assert store.get("missing") is None
    assert {report.incident_id for report in store.list()} == {"a", "b"}
    export = tmp_path / "out" / "incidents.json"
    store.export(export)
    assert len(json.loads(export.read_text())) == 2


def test_store_replaces_rather_than_duplicating(tmp_path):
    store = IncidentStore(tmp_path / "db.sqlite3")
    store.save(_report("a", "NEEDS_INVESTIGATION"))
    store.save(_report("a", "FIXED"))
    assert len(store.list()) == 1
    assert store.get("a").ui_state == "FIXED"


# --------------------------------------------------------------------------- #
# determinism and scheduling
# --------------------------------------------------------------------------- #


def test_pin_seeds_and_reports_what_it_pinned():
    import random

    pinned = determinism.pin(99)
    first = random.random()
    determinism.pin(99)
    assert random.random() == first
    assert pinned["random_seed"] == "99"
    assert "python_version" in pinned


def test_reproduction_seed_records_the_sweep():
    seed = determinism.reproduction_seed(1729, ["a#0", "b#0"], runs=5)
    assert seed["random_seed_sweep"] == "1729..1733"
    assert seed["forced_order"] == "a#0 -> b#0"


def test_deterministic_loop_applies_its_policy():
    assert_supported()
    order: list[int] = []
    loop = DeterministicLoop(lambda ready: list(reversed(ready)))
    try:

        async def record(value: int) -> None:
            order.append(value)

        async def main() -> None:
            await asyncio.gather(record(1), record(2), record(3))

        loop.run_until_complete(main())
    finally:
        loop.close()
    assert sorted(order) == [1, 2, 3]
    assert loop.steps > 0


def test_loop_factory_builds_deterministic_loops():
    loop = loop_factory(list)()
    try:
        assert isinstance(loop, DeterministicLoop)
    finally:
        loop.close()


def test_pct_policy_is_reproducible_for_a_seed():
    handles = [object() for _ in range(5)]
    first = PCTPolicy(seed=7, depth=2, steps=50)(handles)
    second = PCTPolicy(seed=7, depth=2, steps=50)(handles)
    assert [id(item) for item in first] == [id(item) for item in second]
    assert sorted(id(item) for item in first) == sorted(id(item) for item in handles)


def test_pct_bound_falls_with_depth_and_rises_with_runs():
    assert detection_bound(3, 200, 1, 20) > detection_bound(3, 200, 2, 20)
    assert detection_bound(3, 200, 2, 100) > detection_bound(3, 200, 2, 10)
    assert detection_bound(0, 0, 1, 0) == 0.0


# --------------------------------------------------------------------------- #
# harness: the monkeypatch path for uninstrumented code
# --------------------------------------------------------------------------- #

CALLS: list[str] = []


async def uninstrumented_op() -> str:
    CALLS.append("ran")
    return "done"


async def test_patch_targets_gates_uninstrumented_functions():
    reset_occurrences()
    CALLS.clear()
    harness = ScheduleHarness(["gate_me#0"], timeout_s=1.0)
    module = "tests.test_units"
    with patch_targets(harness, {"gate_me#0": f"{module}.uninstrumented_op"}):
        import tests.test_units as this_module

        assert await this_module.uninstrumented_op() == "done"
    assert harness.reached == ["gate_me#0"]
    import tests.test_units as restored

    assert restored.uninstrumented_op.__name__ == "uninstrumented_op"


# --------------------------------------------------------------------------- #
# local provider
# --------------------------------------------------------------------------- #


def _ref(name, access):
    return OperationRef(
        span_name=name,
        occurrence=0,
        source_file="tests/test_m.py",
        source_line=1,
        qualname=name,
        is_test_scope=True,
        access=access,
        resource="s.v",
    )


def _proven(access_a="read", access_b="write"):
    from chronotrace.contracts import CandidateInversion

    inversion = CandidateInversion(
        op_a=_ref("reader", access_a),
        op_b=_ref("writer", access_b),
        causal_position=0,
        ochiai_score=1.0,
        in_backward_slice=True,
        classification="CAUSALLY_SUFFICIENT",
        forced_failure_rate=1.0,
        failing_order=["reader#0", "writer#0"],
    )
    return Diagnosis(status="RACE_PROVEN", proven_inversion=inversion, bug_depth=1)


def test_read_after_write_selects_an_event():
    intent = ReferencePolicyProvider().propose(_proven(), "source")
    assert intent.transformation == "INJECT_ASYNC_EVENT"
    assert intent.signal_site.span_name == "writer"
    assert intent.wait_site.span_name == "reader"


def test_two_independent_writes_recommend_relaxing_the_assertion():
    """Ordering two independent producers would serialise legitimate concurrency."""
    intent = ReferencePolicyProvider().propose(_proven("write", "write"), "source")
    assert intent.transformation == "RELAX_ASSERTION"
    assert intent.primitive == "none"


def test_unproven_diagnosis_gets_no_repair():
    intent = ReferencePolicyProvider().propose(Diagnosis(status="ABSTAINED"), "source")
    assert intent.transformation == "NO_REPAIR"


def test_fixtures_are_recorded_and_replayed(tmp_path):
    provider = ReferencePolicyProvider(fixtures_dir=tmp_path)
    first = provider.propose(_proven(), "source")
    assert list(tmp_path.glob("*.json"))
    replayed = ReferencePolicyProvider(fixtures_dir=tmp_path, replay_only=True)
    assert replayed.propose(_proven(), "source") == first


def test_replay_only_refuses_to_invent_a_response(tmp_path):
    provider = ReferencePolicyProvider(fixtures_dir=tmp_path, replay_only=True)
    with pytest.raises(ProviderError, match="no recorded fixture"):
        provider.propose(_proven(), "source")


def test_local_provider_reports_no_tokens():
    """A token count it made up would be a fabricated metric."""
    provider = ReferencePolicyProvider()
    provider.propose(_proven(), "source")
    assert provider.last_usage == (0, 0)
    assert provider.calls == 1


# --------------------------------------------------------------------------- #
# eval scoring
# --------------------------------------------------------------------------- #


def test_band_aid_scan_uses_the_governor_rules():
    sleepy = "--- a/x\n+++ b/x\n@@\n+    await asyncio.sleep(0.5)\n"
    clean = "--- a/x\n+++ b/x\n@@\n+    await gate.wait()\n"
    assert _contains_band_aid(sleepy)
    assert not _contains_band_aid(clean)
    assert not _contains_band_aid("")


def test_benchmark_corpus_declares_ground_truth():
    cases = load_cases(__import__("pathlib").Path("benchmark/cases"))
    assert len(cases) >= 8
    assert sum(case.is_control for case in cases) >= 3
    assert all(case.expected_ui_state for case in cases)


def test_scores_and_report_render_with_no_results():
    score = score_arm("C", "reference-policy", [])
    assert score.repair_rate is None
    assert score.tokens_per_repair is None
    assert score.median_overhead_ms is None
    markdown = render_markdown([], summarise([]))
    assert "Results" in markdown


def test_arm_scoring_counts_a_verified_repair():
    from chronotrace.contracts import VerificationResult
    from chronotrace.eval.cases import BenchmarkCase

    case = BenchmarkCase(
        case_id="R01",
        name="x",
        test_id="t.py::test_x",
        expected_ui_state="FIXED",
        expected_transformation="INJECT_ASYNC_EVENT",
        expected_abstain_reason=None,
        is_control=False,
        band_aid_would_pass=True,
        shape="race",
        notes="",
        directory=__import__("pathlib").Path("."),
    )
    report = _report()
    report.unified_diff = "--- a/x\n+++ b/x\n@@\n+    await gate.wait()\n"
    report.verification = VerificationResult(
        tier_reached="FORCED_HARMLESS",
        pre_patch_forced_failed=True,
        post_patch_forced_passed=True,
        measured_overhead_ms=0.4,
    )
    score = score_arm("C", "reference-policy", [(case, report)])
    assert score.repair_rate == 1.0
    assert score.band_aid_rate == 0.0
    assert score.median_overhead_ms == 0.4


# --------------------------------------------------------------------------- #
# instrumentation
# --------------------------------------------------------------------------- #


@operation("probe", resource="p.v", access="read")
async def probe() -> int:
    return 1


async def test_instrumentation_is_inert_without_a_recorder():
    """The same test binary runs instrumented and uninstrumented (D3)."""
    from chronotrace.capture.instrument import current_recorder

    assert current_recorder() is None
    assert await probe() == 1


async def test_recorder_captures_occurrence_indexed_spans():
    from chronotrace.capture.instrument import Recorder, assertion, install_recorder

    recorder = Recorder()
    with install_recorder(recorder):
        await probe()
        await probe()
        with pytest.raises(AssertionError), assertion("p.v"):
            raise AssertionError
    keys = [span.key for span in recorder.spans]
    assert keys[:2] == ["probe#0", "probe#1"]
    assert recorder.failing_resource == "p.v"
    assert recorder.spans[-1].attributes["ct.failed"] is True


# --------------------------------------------------------------------------- #
# capture and eval paths that only fire on failure
# --------------------------------------------------------------------------- #


def test_capture_discards_runs_from_a_different_environment(tmp_path, monkeypatch):
    """E2: traces captured in different environments are not comparable."""
    from chronotrace.capture import collect as collect_mod
    from chronotrace.capture.fingerprint import compute
    from chronotrace.contracts import TraceCapture
    from chronotrace.verify.runner import RunOutcome

    base = compute("t::t")
    other = base.model_copy(update={"python_version": "3.99.0"})
    outcomes = [
        RunOutcome(
            passed=False,
            timed_out=False,
            duration_s=0.1,
            capture=TraceCapture(run_id="a", outcome="FAIL", fingerprint=base),
        ),
        RunOutcome(
            passed=True,
            timed_out=False,
            duration_s=0.1,
            capture=TraceCapture(run_id="b", outcome="PASS", fingerprint=other),
        ),
    ]
    calls = iter(outcomes)
    monkeypatch.setattr(collect_mod, "run_test", lambda *a, **k: next(calls))
    bundle = collect_mod.collect("t::t", cwd=tmp_path, runs=2)
    assert bundle.fingerprint_conflicts == 1
    assert not bundle.has_pair


def test_capture_counts_timeouts_separately_from_failures(tmp_path, monkeypatch):
    """A hung run is a deadlock signal, not a flaky failure (INV-4)."""
    from chronotrace.capture import collect as collect_mod
    from chronotrace.verify.runner import RunOutcome

    monkeypatch.setattr(
        collect_mod,
        "run_test",
        lambda *a, **k: RunOutcome(passed=False, timed_out=True, duration_s=30.0),
    )
    bundle = collect_mod.collect("t::t", cwd=tmp_path, runs=3)
    assert bundle.runs_timed_out == 3
    assert not bundle.has_pair


def test_baseline_arms_are_refused_on_the_reference_policy(tmp_path):
    """A baseline drawn from our own policy would describe this repo, not a model."""
    from chronotrace.config import Settings
    from chronotrace.eval.arms import run_arm

    for arm in ("A", "B"):
        result = run_arm(
            arm,
            [],
            cwd=tmp_path,
            provider=ReferencePolicyProvider(),
            settings=Settings(),
        )
        assert result.results == []
        assert result.skipped_reason is not None
        assert "hand-written decision policy" in result.skipped_reason


def test_report_names_the_arm_that_could_not_run(tmp_path):
    from chronotrace.eval.arms import ArmResult
    from chronotrace.eval.report import render_markdown, summarise, write_report

    skipped = ArmResult(arm="A", provider="local", results=[], skipped_reason="needs a model")
    markdown = render_markdown([skipped], summarise([skipped]))
    assert "Arm A did not run" in markdown
    assert "needs a model" in markdown
    markdown_path, json_path = write_report([skipped], tmp_path / "out")
    assert markdown_path.exists() and json_path.exists()
    assert json.loads(json_path.read_text())["arms"][0]["skipped_reason"] == "needs a model"


# --------------------------------------------------------------------------- #
# intent retry
# --------------------------------------------------------------------------- #


class _ScriptedProvider:
    """Returns a scripted sequence of results, recording the feedback it saw."""

    name = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.seen_errors = []
        self.context = {}
        self._usage = (7, 3)
        self.calls = 0

    @property
    def last_usage(self):
        return self._usage

    def propose(self, diagnosis, source, previous_error=None):
        self.seen_errors.append(previous_error)
        self.calls += 1
        result = self.script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _good_intent():
    from chronotrace.contracts import RepairIntent

    return RepairIntent(
        transformation="INJECT_ASYNC_EVENT",
        shared_scope="FIXTURE",
        primitive="asyncio.Event",
        signal_site=_ref("writer", "write"),
        wait_site=_ref("reader", "read"),
        rationale="x",
    )


def test_a_rejected_intent_is_retried_with_the_validator_error():
    from chronotrace.errors import ProviderError
    from chronotrace.pipeline import _propose_with_retry

    provider = _ScriptedProvider([ProviderError("requires wait_site"), _good_intent()])
    intent, attempts = _propose_with_retry(provider, _proven(), "src", max_retries=2)
    assert intent is not None
    assert [a.accepted for a in attempts] == [False, True]
    assert provider.seen_errors == [None, "requires wait_site"]


def test_every_attempt_is_recorded_and_its_tokens_counted():
    from chronotrace.errors import ProviderError
    from chronotrace.pipeline import _propose_with_retry

    provider = _ScriptedProvider([ProviderError("bad"), ProviderError("still bad"), _good_intent()])
    _intent, attempts = _propose_with_retry(provider, _proven(), "src", max_retries=2)
    assert [a.attempt for a in attempts] == [1, 2, 3]
    assert sum(a.tokens_input for a in attempts) == 21
    assert sum(a.tokens_output for a in attempts) == 9


def test_retries_are_bounded_and_then_give_up():
    """An unbounded loop against a model that cannot comply is a spend."""
    from chronotrace.errors import ProviderError
    from chronotrace.pipeline import _propose_with_retry

    provider = _ScriptedProvider([ProviderError("nope")] * 5)
    intent, attempts = _propose_with_retry(provider, _proven(), "src", max_retries=2)
    assert intent is None
    assert len(attempts) == 3
    assert provider.calls == 3


def test_each_attempt_is_keyed_separately_for_recording():
    from chronotrace.errors import ProviderError
    from chronotrace.pipeline import _propose_with_retry

    provider = _ScriptedProvider([ProviderError("bad"), _good_intent()])
    provider.context = {"arm": "C", "case": "R01", "attempt": "1"}
    _propose_with_retry(provider, _proven(), "src", max_retries=2)
    assert provider.context["attempt"] == "2"
