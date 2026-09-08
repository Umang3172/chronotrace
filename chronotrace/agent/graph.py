"""The Strands agent loop, and the AgentCore entrypoint (spec 19.4, A-6).

The loop is genuinely agentic — it takes actions, observes results, and decides
what to do next, including deciding to abstain — while every piece of authority
stays deterministic. The model chooses which candidate to force and which repair
pattern fits; it never decides whether a patch is permitted, and it never writes
source.

Strands is imported lazily so that the whole pipeline, the benchmark and the
eval harness remain runnable with no cloud dependency at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from chronotrace.agent.tools import AgentTools
from chronotrace.config import Settings, get_settings
from chronotrace.contracts import IncidentReport
from chronotrace.errors import ConfigurationError
from chronotrace.logging import get_logger
from chronotrace.pipeline import repair
from chronotrace.providers.base import ModelProvider
from chronotrace.providers.reference_policy import PROVIDER_LABEL, ReferencePolicyProvider

if TYPE_CHECKING:  # the SDK is an optional extra and must stay out of the runtime graph
    from strands import Agent

log = get_logger(__name__)

__all__ = ["SYSTEM_PROMPT", "build_agent", "handler"]

SYSTEM_PROMPT = """You investigate a flaky asyncio test and decide what to do about it.

Work in steps, using the tools:

1. capture_traces  - gather a comparable passing and failing execution.
2. trace_slice     - see what the failed assertion actually depended on.
3. compare_orderings - see which orderings differ between passing and failing runs.
4. force_replay    - force a candidate ordering. This is how you decide, not guess:
                     a forced failure rate of 1.0 means that ordering is a sufficient
                     condition for the failure; 0.0 means it is noise; anything in
                     between means the bug needs more than one constraint.
5. source_context  - read the code around an operation before proposing anything.
6. check_patch     - ask the governor whether a patch would be permitted.

Then decide: repair, investigate further, or abstain.

Abstaining is a correct outcome and is often the right one. Abstain when the
nondeterminism is in the data rather than the schedule, when no ordering
reproduces the failure, when the race needs two or more constraints, or when the
race lives in application code rather than the test.

You never write source code. You return a repair intent describing which
transformation to apply and where. Sleeps, retries, timeout increases, weakened
assertions and skips are rejected automatically; proposing one wastes a round."""


def build_agent(test_id: str, cwd: Path, settings: Settings | None = None) -> Agent:
    """Build a Strands agent bound to one incident's tools.

    Args:
        test_id: The flaky test to investigate.
        cwd: Repository root.
        settings: Runtime settings; defaults to the process settings.

    Returns:
        A configured Strands ``Agent``. The name is only imported under
        ``TYPE_CHECKING``: the SDK is an optional extra, so importing it for
        real here would make the whole package need it just to import.

    Raises:
        ConfigurationError: Strands is not installed, or no model id is set.

    """
    settings = settings or get_settings()
    try:
        from strands import Agent
        from strands.models import BedrockModel
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ConfigurationError(
            "the Strands agent loop needs the SDK: uv sync --extra bedrock"
        ) from exc
    from chronotrace.providers.bedrock import DEFAULT_BEDROCK_MODEL

    model_id = settings.model_id_large or DEFAULT_BEDROCK_MODEL
    tools = AgentTools(test_id, cwd, timeout_s=settings.run_timeout_s)
    return Agent(
        model=BedrockModel(model_id=model_id, region_name=settings.aws_region),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            tools.capture_traces,
            tools.trace_slice,
            tools.compare_orderings,
            tools.force_replay,
            tools.source_context,
            tools.diagnose_now,
            tools.check_patch,
            tools.run_once,
        ],
    )


def handler(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore Runtime entrypoint.

    Two modes, because they answer different questions. ``agent`` runs the
    Strands loop, which decides for itself what evidence to gather and whether
    the evidence supports a repair at all; it is the default, since deciding is
    what an agent runtime is for. ``pipeline`` runs the fixed sequence and
    returns the full incident report, which is the reproducible artifact.

    Args:
        payload: ``{"test_id": ..., "cwd": ..., "mode": "agent"|"pipeline",
            "runs": 20, "apply": false}``.

    Returns:
        Primitive JSON (E4). Nothing that is not JSON-serializable crosses this
        boundary: a raw span or CST node here is how a runtime ends up
        serializing an object into a fallback string and exceeding its payload
        limit.

    """
    test_id = payload["test_id"]
    cwd = Path(payload.get("cwd", "."))
    settings = get_settings()
    if payload.get("mode", "agent") == "agent":
        return _run_agent(test_id, cwd, settings)
    provider = (
        ReferencePolicyProvider(fixtures_dir=settings.fixtures_dir)
        if settings.provider == PROVIDER_LABEL
        else _bedrock(settings)
    )
    report: IncidentReport = repair(
        test_id,
        cwd=cwd,
        provider=provider,
        settings=settings,
        capture_runs=int(payload.get("runs", 20)),
        apply=bool(payload.get("apply", False)),
    )
    return {"mode": "pipeline", "report": report.model_dump(mode="json")}


def _run_agent(test_id: str, cwd: Path, settings: Settings) -> dict[str, Any]:
    """Run the Strands loop and flatten its result to primitive JSON."""
    agent = build_agent(test_id, cwd, settings)
    result = agent(f"Investigate {test_id} and decide what to do about it.")
    return {
        "mode": "agent",
        "test_id": test_id,
        "stop_reason": str(result.stop_reason),
        "cycles": int(result.metrics.cycle_count),
        "tool_calls": {
            name: int(metric.call_count)
            for name, metric in sorted(result.metrics.tool_metrics.items())
            if metric.call_count
        },
        "usage": {
            key: value
            for key, value in result.metrics.accumulated_usage.items()
            if isinstance(value, int)
        },
        "conclusion": "".join(
            block.get("text", "") for block in result.message.get("content", []) if "text" in block
        ),
    }


def _bedrock(settings: Settings) -> ModelProvider:
    from chronotrace.providers.bedrock import BedrockProvider

    return BedrockProvider(settings)
