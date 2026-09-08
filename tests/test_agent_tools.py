"""The agent's tool surface must actually reach the SDK.

These are regression guards for a failure that is silent by construction:
Strands logs `unrecognized tool specification` and carries on, so an agent built
from undecorated methods constructs fine, reports no error, and runs with no
tools at all. Nothing downstream notices, because a model with no tools still
answers. The only way to catch it is to assert the registration.
"""

from pathlib import Path

import pytest

from chronotrace.agent.tools import AgentTools
from chronotrace.config import Settings

pytest.importorskip("strands", reason="the agent loop is behind the bedrock extra")

TOOL_NAMES = [
    "capture_traces",
    "trace_slice",
    "compare_orderings",
    "force_replay",
    "source_context",
    "diagnose_now",
    "check_patch",
    "run_once",
]

TEST_ID = (
    "benchmark/cases/R01_unawaited_writer/test_R01_unawaited_writer.py"
    "::test_reader_sees_committed_value"
)


@pytest.fixture
def tools():
    return AgentTools(TEST_ID, Path())


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_every_tool_carries_a_spec(tools, name):
    """An undecorated method has no spec, and Strands drops it without erroring."""
    spec = getattr(getattr(tools, name), "tool_spec", None)
    assert spec is not None, f"{name} would be dropped as an unrecognized tool specification"
    assert spec["name"] == name
    assert spec["description"].strip()


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_self_never_leaks_into_the_input_schema(tools, name):
    """A bound method that advertises `self` asks the model for an object it cannot make."""
    schema = getattr(tools, name).tool_spec["inputSchema"]["json"]
    assert "self" not in schema.get("properties", {})
    assert "self" not in schema.get("required", [])


def test_build_agent_registers_every_tool():
    """The whole point: the agent ends up holding all eight, not zero."""
    from chronotrace.agent.graph import build_agent

    agent = build_agent(TEST_ID, Path(), Settings(aws_region="us-east-1"))
    assert sorted(agent.tool_names) == sorted(TOOL_NAMES)


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_tools_stay_callable_as_plain_python(tools, name):
    """Decorating must not cost the direct call the pipeline and the tests use."""
    assert callable(getattr(tools, name))


def test_source_context_reads_real_source(tools):
    """One end-to-end call, to prove the decorator wraps a working function."""
    result = tools.source_context(path="chronotrace/agent/tools.py", line=1, window=2)
    assert "path" in result
    assert "AgentTools" in result["source"] or result["source"].strip()


def test_source_context_reports_a_missing_file_rather_than_raising(tools):
    """A tool that raises ends the loop; one that reports lets the agent recover."""
    assert "error" in tools.source_context(path="does/not/exist.py", line=1)


class _FakeMetrics:
    def __init__(self, tool_metrics):
        self.cycle_count = 3
        self.accumulated_usage = {"inputTokens": 3066, "outputTokens": 286, "totalTokens": 3352}
        self.tool_metrics = tool_metrics


class _FakeMetric:
    def __init__(self, call_count):
        self.call_count = call_count


class _FakeResult:
    def __init__(self):
        self.stop_reason = "end_turn"
        self.message = {"content": [{"text": "Abstained: no ordering reproduces the failure."}]}
        self.metrics = _FakeMetrics(
            {
                "capture_traces": _FakeMetric(1),
                "force_replay": _FakeMetric(2),
                "run_once": _FakeMetric(0),
            }
        )


def test_handler_defaults_to_the_agent_loop(monkeypatch):
    """An agent runtime that quietly runs the fixed pipeline is not an agent runtime."""
    from chronotrace.agent import graph

    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: lambda prompt: _FakeResult())
    result = graph.handler({"test_id": TEST_ID})

    assert result["mode"] == "agent"
    assert result["cycles"] == 3
    assert result["conclusion"].startswith("Abstained")
    assert result["usage"]["inputTokens"] == 3066


def test_handler_reports_only_tools_that_were_actually_called(monkeypatch):
    """A tool listed with zero calls reads as evidence of work that never happened."""
    from chronotrace.agent import graph

    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: lambda prompt: _FakeResult())
    calls = graph.handler({"test_id": TEST_ID})["tool_calls"]

    assert calls == {"capture_traces": 1, "force_replay": 2}


def test_handler_pipeline_mode_still_returns_a_report(monkeypatch):
    """The deterministic path stays reachable; it is the reproducible artifact."""
    from chronotrace.agent import graph

    class _Report:
        def model_dump(self, mode="json"):
            return {"incident_id": "abc123", "ui_state": "ABSTAINED"}

    monkeypatch.setattr(graph, "repair", lambda *a, **k: _Report())
    result = graph.handler({"test_id": TEST_ID, "mode": "pipeline"})

    assert result["mode"] == "pipeline"
    assert result["report"]["incident_id"] == "abc123"
