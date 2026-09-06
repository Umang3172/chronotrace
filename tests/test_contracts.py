"""Contracts are the boundary between stages; these tests pin the guarantees they carry."""

import json

import pytest
from pydantic import ValidationError

from chronotrace.capture.fingerprint import comparable, compute
from chronotrace.contracts import (
    CandidateInversion,
    CaptureBundle,
    Diagnosis,
    IncidentReport,
    OperationRef,
    RepairIntent,
    SpanRecord,
    TraceCapture,
)


def test_span_and_operation_keys_are_occurrence_indexed():
    span = SpanRecord(span_id="a", name="select", occurrence=3, start_ns=1, end_ns=2)
    ref = OperationRef(
        span_name="select",
        occurrence=3,
        source_file="a.py",
        source_line=1,
        qualname="select",
        is_test_scope=True,
    )
    assert span.key == ref.key == "select#3"


def test_reports_serialize_to_primitive_json():
    """E4: non-serializable state in the agent aborts the runtime."""
    report = IncidentReport(
        incident_id="x",
        test_id="t::t",
        ui_state="ABSTAINED",
        diagnosis=Diagnosis(status="ABSTAINED", abstain_reason="NO_INVERSION"),
    )
    round_tripped = json.loads(report.model_dump_json())
    assert round_tripped["ui_state"] == "ABSTAINED"
    assert IncidentReport.model_validate(round_tripped) == report


def test_unknown_states_are_rejected():
    with pytest.raises(ValidationError):
        Diagnosis(status="PROBABLY_FINE")
    with pytest.raises(ValidationError):
        RepairIntent(transformation="INSERT_SLEEP", shared_scope="NONE", primitive="none")


def test_capture_bundle_reports_probe_effect_only_when_measured():
    bundle = CaptureBundle(test_id="t::t", natural_flake_rate=0.4)
    assert bundle.probe_effect_delta is None
    bundle.uninstrumented_flake_rate = 0.5
    assert bundle.probe_effect_delta == pytest.approx(-0.1)


def test_capture_bundle_requires_both_outcomes_for_a_pair():
    fingerprint = compute("t::t")
    bundle = CaptureBundle(test_id="t::t")
    assert not bundle.has_pair
    bundle.failing.append(TraceCapture(run_id="f", outcome="FAIL", fingerprint=fingerprint))
    assert not bundle.has_pair
    bundle.passing.append(TraceCapture(run_id="p", outcome="PASS", fingerprint=fingerprint))
    assert bundle.has_pair


def test_fingerprints_gate_comparability():
    left = compute("t::t")
    right = left.model_copy(update={"python_version": "3.99.0"})
    assert comparable(left, left)
    assert not comparable(left, right)


def test_candidates_start_untested():
    """A candidate is a suspicion until it has been forced."""
    ref = OperationRef(
        span_name="w",
        occurrence=0,
        source_file="a.py",
        source_line=1,
        qualname="w",
        is_test_scope=True,
    )
    candidate = CandidateInversion(
        op_a=ref, op_b=ref, causal_position=0, ochiai_score=1.0, in_backward_slice=True
    )
    assert candidate.classification == "UNTESTED"
    assert candidate.forced_failure_rate is None
