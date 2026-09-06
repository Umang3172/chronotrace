"""Abstention is a first-class outcome (INV-5); each refusal path gets a test."""

from pathlib import Path

from chronotrace.capture.fingerprint import compute
from chronotrace.contracts import CaptureBundle, SpanRecord, TraceCapture
from chronotrace.diagnose.abstain import (
    assertion_failed,
    detect_paradigm,
    nondeterministic_sources,
)
from chronotrace.diagnose.engine import diagnose


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body)
    return path


def test_detects_threading_and_multiprocessing(tmp_path):
    assert detect_paradigm(_write(tmp_path, "a.py", "import threading\n")) == "threading"
    assert (
        detect_paradigm(_write(tmp_path, "b.py", "import multiprocessing\n")) == "multiprocessing"
    )
    assert detect_paradigm(_write(tmp_path, "c.py", "import asyncio\n")) == "asyncio"
    assert detect_paradigm(_write(tmp_path, "d.py", "x = 1\n")) == "unknown"


def test_multiprocessing_wins_over_asyncio(tmp_path):
    """A module using both is still out of scope."""
    source = "import asyncio\nimport multiprocessing\n"
    assert detect_paradigm(_write(tmp_path, "e.py", source)) == "multiprocessing"


def test_reports_nondeterministic_data_sources(tmp_path):
    path = _write(tmp_path, "f.py", "import random\n\nx = random.random()\n")
    found = nondeterministic_sources(path)
    assert any("random" in item for item in found)


def test_assertion_failure_is_distinguished_from_a_raised_exception():
    fingerprint = compute("tests/test_x.py::test_y")
    spans = [
        SpanRecord(
            span_id="a",
            name="assert",
            occurrence=0,
            start_ns=1,
            end_ns=2,
            attributes={"ct.assertion": True, "ct.failed": True},
        )
    ]
    failed = TraceCapture(run_id="r1", outcome="FAIL", fingerprint=fingerprint, spans=spans)
    raised = TraceCapture(run_id="r2", outcome="FAIL", fingerprint=fingerprint, spans=[])
    assert assertion_failed(failed)
    assert not assertion_failed(raised)


def test_threading_abstains_before_anything_else_runs(tmp_path):
    path = tmp_path / "test_t.py"
    path.write_text("import threading\n")
    bundle = CaptureBundle(test_id=f"{path.name}::test_t")
    result = diagnose(bundle, cwd=tmp_path)
    assert result.status == "ABSTAINED"
    assert result.abstain_reason == "NON_ASYNCIO_PARADIGM"
    assert "asyncio" in result.explanation


def test_missing_trace_pair_abstains(tmp_path):
    path = tmp_path / "test_u.py"
    path.write_text("import asyncio\n")
    fingerprint = compute("test_u.py::test_u")
    bundle = CaptureBundle(
        test_id=f"{path.name}::test_u",
        failing=[TraceCapture(run_id="r", outcome="FAIL", fingerprint=fingerprint, spans=[])],
        runs_executed=20,
    )
    result = diagnose(bundle, cwd=tmp_path)
    assert result.status == "ABSTAINED"
    assert result.abstain_reason == "NO_TRACE_PAIR"
    assert "only failing runs" in result.explanation


def test_coarse_granularity_abstains_rather_than_localising_wrongly(tmp_path):
    path = tmp_path / "test_v.py"
    path.write_text("import asyncio\n")
    fingerprint = compute("test_v.py::test_v")
    span = SpanRecord(
        span_id="s",
        name="update_fixture",
        occurrence=0,
        start_ns=1,
        end_ns=2,
        attributes={"ct.resource": "s.v", "ct.access": "write"},
    )
    bundle = CaptureBundle(
        test_id=f"{path.name}::test_v",
        passing=[TraceCapture(run_id="p", outcome="PASS", fingerprint=fingerprint, spans=[span])],
        failing=[
            TraceCapture(
                run_id="f",
                outcome="FAIL",
                fingerprint=fingerprint,
                spans=[span],
                failing_resource="s.v",
            )
        ],
    )
    result = diagnose(bundle, cwd=tmp_path)
    assert result.abstain_reason == "SPAN_GRANULARITY_TOO_COARSE"
