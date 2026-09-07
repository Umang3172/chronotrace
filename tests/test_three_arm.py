"""The baseline harness. Its correctness is what makes the comparison mean anything.

The risk these guard against is a rigged comparison: a baseline judged by looser
rules than Arm C, or given a prompt that steers it away from the very behaviour
the experiment exists to measure.
"""

import json

import pytest

from chronotrace.capture.fingerprint import compute
from chronotrace.contracts import (
    CandidateInversion,
    CaptureBundle,
    Diagnosis,
    OperationRef,
    SpanRecord,
    TraceCapture,
)
from chronotrace.errors import ProviderError
from chronotrace.eval.bandaid import scan
from chronotrace.eval.baseline import build_prompt, strip_fences
from chronotrace.eval.cases import BenchmarkCase
from chronotrace.eval.replay_check import compare
from chronotrace.providers.record import CallRecord, FixtureProvider, FixtureRecorder

# --------------------------------------------------------------------------- #
# band-aid scanning
# --------------------------------------------------------------------------- #


def test_band_aid_scan_uses_the_governor_rules_not_a_looser_copy():
    """All three arms must be judged by identical rules."""
    from chronotrace.govern.negative import check_negative

    before = "import asyncio\n\n\nasync def t():\n    assert x == 1\n"
    after = "import asyncio\n\n\nasync def t():\n    await asyncio.sleep(0.5)\n    assert x == 1\n"
    assert scan(before, after).rule_ids == sorted(
        {f.rule_id for f in check_negative(before, after)}
    )


@pytest.mark.parametrize(
    ("patch", "rule"),
    [
        ("    await asyncio.sleep(0.5)\n    assert x == 1\n", "N1"),
        ("    _s(0.5)\n    assert x == 1\n", "N2"),
        ("    while True:\n        if x == 1:\n            break\n    assert x == 1\n", "N5"),
        ("    assert x in {1, None}\n", "N6"),
        ("    try:\n        assert x == 1\n    except AssertionError:\n        pass\n", "N7"),
    ],
)
def test_each_band_aid_shape_is_detected(patch, rule):
    before = "import asyncio\nfrom time import sleep as _s\n\n\nasync def t():\n    assert x == 1\n"
    after = "import asyncio\nfrom time import sleep as _s\n\n\nasync def t():\n" + patch
    assert rule in scan(before, after).rule_ids


def test_sleep_duration_is_summed_for_the_ci_cost_metric():
    before = "import asyncio\n\n\nasync def t():\n    pass\n"
    after = (
        "import asyncio\n\n\nasync def t():\n"
        "    await asyncio.sleep(0.25)\n    await asyncio.sleep(1.5)\n"
    )
    assert scan(before, after).sleep_seconds == pytest.approx(1.75)


def test_a_zero_duration_sleep_is_still_a_band_aid_but_costs_nothing():
    """`asyncio.sleep(0)` is a yield: banned as a timing fix, but free in CI."""
    before = "import asyncio\n\n\nasync def t():\n    pass\n"
    after = "import asyncio\n\n\nasync def t():\n    await asyncio.sleep(0)\n"
    result = scan(before, after)
    assert result.is_band_aid and result.rule_ids == ["N1"]
    assert result.sleep_seconds == 0.0


def test_computed_sleep_durations_make_the_ci_cost_a_lower_bound():
    before = "import asyncio\n\n\nasync def t():\n    pass\n"
    after = "import asyncio\n\n\nasync def t():\n    await asyncio.sleep(delay * 2)\n"
    result = scan(before, after)
    assert result.is_band_aid
    assert result.sleep_seconds == 0.0


def test_unparseable_patch_is_reported_rather_than_scanned():
    assert scan("x = 1\n", "def broken(:\n").parse_error is not None


# --------------------------------------------------------------------------- #
# prompts
# --------------------------------------------------------------------------- #


def _bundle_and_diagnosis():
    fingerprint = compute("t.py::test_x")

    def span(name, occ, start, access):
        return SpanRecord(
            span_id=f"{name}{occ}",
            name=name,
            occurrence=occ,
            start_ns=start,
            end_ns=start + 5,
            task_name="Task-1",
            attributes={"ct.resource": "s.v", "ct.access": access},
        )

    bundle = CaptureBundle(
        test_id="t.py::test_x",
        passing=[
            TraceCapture(
                run_id="p",
                outcome="PASS",
                fingerprint=fingerprint,
                spans=[span("w", 0, 1, "write"), span("r", 0, 2, "read")],
            )
        ],
        failing=[
            TraceCapture(
                run_id="f",
                outcome="FAIL",
                fingerprint=fingerprint,
                spans=[span("r", 0, 1, "read")],
                failure_message="AssertionError: assert None == 'ready'",
            )
        ],
        runs_executed=20,
        natural_flake_rate=0.5,
    )
    ref = OperationRef(
        span_name="r",
        occurrence=0,
        source_file="t.py",
        source_line=1,
        qualname="r",
        is_test_scope=True,
        access="read",
        resource="s.v",
    )
    diagnosis = Diagnosis(
        status="RACE_PROVEN",
        proven_inversion=CandidateInversion(
            op_a=ref,
            op_b=ref,
            causal_position=0,
            ochiai_score=1.0,
            in_backward_slice=True,
            classification="CAUSALLY_SUFFICIENT",
            forced_failure_rate=1.0,
            failing_order=["r#0", "w#0"],
        ),
        candidates=[
            CandidateInversion(
                op_a=ref,
                op_b=ref,
                causal_position=0,
                ochiai_score=1.0,
                in_backward_slice=True,
                classification="CAUSALLY_SUFFICIENT",
                forced_failure_rate=1.0,
                failing_order=["r#0", "w#0"],
            )
        ],
    )
    return bundle, diagnosis


def _case():
    from pathlib import Path

    return BenchmarkCase(
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
        directory=Path(),
    )


BANNED_HINTS = (
    "sleep",
    "synchron",
    "asyncio.Event",
    "barrier",
    "primitive",
    "retry",
    "timeout",
    "governor",
    "policy",
    "band-aid",
)


def test_arm_a_prompt_contains_no_hint_about_the_answer():
    """Any nudge invalidates the arm: it exists to measure the default behaviour."""
    bundle, diagnosis = _bundle_and_diagnosis()
    prompt = build_prompt("A", _case(), "source", bundle, diagnosis).lower()
    for hint in BANNED_HINTS:
        assert hint not in prompt, f"Arm A prompt leaks a hint: {hint!r}"


def test_arm_a_prompt_carries_the_code_and_the_failure():
    bundle, diagnosis = _bundle_and_diagnosis()
    prompt = build_prompt("A", _case(), "SOURCE_MARKER", bundle, diagnosis)
    assert "SOURCE_MARKER" in prompt
    assert "AssertionError" in prompt
    assert "failed 1 of 20 runs" in prompt


def test_arm_a_prompt_has_no_trace_evidence():
    bundle, diagnosis = _bundle_and_diagnosis()
    prompt = build_prompt("A", _case(), "source", bundle, diagnosis)
    assert "suspiciousness" not in prompt.lower()
    assert "Operation order" not in prompt


def test_arm_b_adds_evidence_and_still_no_hint():
    bundle, diagnosis = _bundle_and_diagnosis()
    prompt = build_prompt("B", _case(), "source", bundle, diagnosis)
    assert "Operation order in a passing run" in prompt
    assert "suspiciousness 1.00" in prompt
    assert "Identified inverted operation pair" in prompt
    lowered = prompt.lower()
    for hint in BANNED_HINTS:
        assert hint not in lowered, f"Arm B prompt leaks a hint: {hint!r}"


def test_arm_b_evidence_excludes_forced_replay_results():
    """Forced replay belongs to Arm C's diagnosis, not to the trace diff."""
    bundle, diagnosis = _bundle_and_diagnosis()
    prompt = build_prompt("B", _case(), "source", bundle, diagnosis).lower()
    assert "forced" not in prompt
    assert "100%" not in prompt


def test_arm_b_reports_honestly_when_there_is_no_inversion():
    bundle, _ = _bundle_and_diagnosis()
    prompt = build_prompt("B", _case(), "source", bundle, Diagnosis(status="ABSTAINED"))
    assert "No ordering difference was found" in prompt


def test_markdown_fences_are_stripped_so_the_baseline_is_not_penalised():
    assert strip_fences("```python\nx = 1\n```") == "x = 1"
    assert strip_fences("```\nx = 1\n```") == "x = 1"
    assert strip_fences("x = 1") == "x = 1"


# --------------------------------------------------------------------------- #
# fixture recording and replay
# --------------------------------------------------------------------------- #


def _record(tmp_path, response='{"transformation": "NO_REPAIR"}'):
    recorder = FixtureRecorder(tmp_path)
    call = CallRecord(
        provider="ollama:qwen3:8b",
        system="SYS",
        user="USER",
        schema_name="RepairIntent",
        response=response,
        tokens_input=10,
        tokens_output=5,
        seconds=1.0,
        arm="C",
        case_id="R01",
        attempt=1,
    )
    recorder.record(call)
    return recorder, call


def test_recorded_calls_round_trip_by_key(tmp_path):
    recorder, call = _record(tmp_path)
    loaded = recorder.load(call.key)
    assert loaded == call
    assert json.loads((tmp_path / f"{call.key}.json").read_text())["arm"] == "C"


def test_replay_returns_the_recorded_response(tmp_path):
    _record(tmp_path, response="RESPONSE")
    provider = FixtureProvider(tmp_path, provider_label="ollama:qwen3:8b")
    provider.context = {"arm": "C", "case": "R01", "attempt": "1"}
    assert provider.replay(system="SYS", user="USER") == "RESPONSE"
    assert provider.last_usage == (10, 5)
    assert provider.calls == 1


def test_replay_survives_prompt_drift_but_reports_it(tmp_path):
    """Prompts embed the observed flake rate, which changes every run.

    Keying on prompt text would mean a replay could never find its own
    recording. The prompt is compared and any difference is surfaced.
    """
    _record(tmp_path, response="RESPONSE")
    provider = FixtureProvider(tmp_path, provider_label="ollama:qwen3:8b")
    provider.context = {"arm": "C", "case": "R01", "attempt": "1"}
    assert provider.replay(system="SYS", user="A DIFFERENT PROMPT") == "RESPONSE"
    assert provider.prompt_drift == ["C/R01"]


def test_identical_prompts_report_no_drift(tmp_path):
    _record(tmp_path, response="RESPONSE")
    provider = FixtureProvider(tmp_path, provider_label="ollama:qwen3:8b")
    provider.context = {"arm": "C", "case": "R01", "attempt": "1"}
    provider.replay(system="SYS", user="USER")
    assert provider.prompt_drift == []


def test_replay_refuses_to_contact_a_model_when_a_fixture_is_missing(tmp_path):
    """A replay that silently regenerates is not a replay."""
    _record(tmp_path)
    provider = FixtureProvider(tmp_path, provider_label="ollama:qwen3:8b")
    provider.context = {"arm": "A", "case": "R99", "attempt": "1"}
    with pytest.raises(ProviderError, match="no recorded call"):
        provider.replay(system="SYS", user="USER")


def test_fixture_keys_separate_arms_cases_and_attempts(tmp_path):
    """The same prompt in two arms must not collide."""
    recorder = FixtureRecorder(tmp_path)
    base = {
        "provider": "p",
        "system": "S",
        "user": "U",
        "schema_name": "s",
        "response": "r",
        "tokens_input": 1,
        "tokens_output": 1,
        "seconds": 0.1,
        "attempt": 1,
    }
    a = CallRecord(**base, arm="A", case_id="R01")
    b = CallRecord(**base, arm="B", case_id="R01")
    recorder.record(a)
    recorder.record(b)
    assert a.key != b.key
    assert recorder.count() == 2


# --------------------------------------------------------------------------- #
# replay comparison
# --------------------------------------------------------------------------- #


def _results(tmp_path, name, *, tokens=10, tier="FORCED_HARMLESS"):
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "arm": "A",
                        "case_id": "R01",
                        "band_aid": True,
                        "band_aid_rules": ["N1"],
                        "band_aid_detail": "N1: sleep",
                        "modified_file": True,
                        "sleep_seconds_added": 0.5,
                        "tokens_input": tokens,
                        "tokens_output": 5,
                        "model_calls": 1,
                        "attempts_used": 1,
                        "wall_clock_s": 12.0,
                        "ui_state": "FIXED",
                        "verified_repair": True,
                        "tier_reached": tier,
                    }
                ]
            }
        )
    )
    return path


def test_identical_model_derived_fields_pass_the_replay_check(tmp_path):
    live = _results(tmp_path, "live.json")
    replay = _results(tmp_path, "replay.json")
    result = compare(live, replay)
    assert result.model_derived_identical
    assert not result.exact_mismatches


def test_a_changed_token_count_fails_the_replay_check(tmp_path):
    live = _results(tmp_path, "live.json", tokens=10)
    replay = _results(tmp_path, "replay.json", tokens=11)
    result = compare(live, replay)
    assert not result.model_derived_identical
    assert any("tokens_input" in m for m in result.exact_mismatches)


def test_execution_derived_drift_is_reported_but_does_not_fail(tmp_path):
    """Flake rates and timings differ between runs by design."""
    live = _results(tmp_path, "live.json", tier="FORCED_HARMLESS")
    replay = _results(tmp_path, "replay.json", tier="STATISTICAL")
    result = compare(live, replay)
    assert result.model_derived_identical
    assert any("tier_reached" in d for d in result.drifted)


def test_a_missing_arm_case_pair_fails_the_replay_check(tmp_path):
    live = _results(tmp_path, "live.json")
    empty = tmp_path / "replay.json"
    empty.write_text(json.dumps({"results": []}))
    assert not compare(live, empty).model_derived_identical


def test_fixture_keys_ignore_prompt_content(tmp_path):
    """Identity is which call was made, not what the prompt happened to say."""
    from chronotrace.providers.record import fixture_key

    base = {"provider": "p", "arm": "A", "case_id": "R01", "attempt": 1}
    assert fixture_key(**base) == fixture_key(**base)
    assert fixture_key(**base) != fixture_key(**{**base, "attempt": 2})
    assert fixture_key(**base) != fixture_key(**{**base, "arm": "B"})
    assert fixture_key(**base) != fixture_key(**{**base, "case_id": "R02"})
