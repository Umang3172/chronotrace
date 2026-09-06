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
from typing import Any

from chronotrace.agent.tools import AgentTools
from chronotrace.config import Settings, get_settings
from chronotrace.contracts import IncidentReport
from chronotrace.errors import ConfigurationError
from chronotrace.logging import get_logger
from chronotrace.pipeline import repair
from chronotrace.providers.base import ModelProvider
from chronotrace.providers.local import LocalModelProvider

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


def build_agent(test_id: str, cwd: Path, settings: Settings | None = None) -> object:
    """Build a Strands agent bound to one incident's tools.

    Args:
        test_id: The flaky test to investigate.
        cwd: Repository root.
        settings: Runtime settings; defaults to the process settings.

    Returns:
        A configured Strands ``Agent``. Typed as ``object`` because the SDK
        is an optional dependency and must not appear in the import graph.

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
    if not settings.model_id_large:
        raise ConfigurationError(
            "CHRONOTRACE_MODEL_ID_LARGE is unset; Bedrock model ids differ by region "
            "and release, so ChronoTrace will not guess one"
        )
    tools = AgentTools(test_id, cwd, timeout_s=settings.run_timeout_s)
    return Agent(
        model=BedrockModel(model_id=settings.model_id_large, region_name=settings.aws_region),
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

    Args:
        payload: ``{"test_id": ..., "cwd": ..., "apply": false}``.

    Returns:
        The incident report as primitive JSON (E4). Nothing that is not
        JSON-serializable crosses this boundary.

    """
    test_id = payload["test_id"]
    cwd = Path(payload.get("cwd", "."))
    settings = get_settings()
    provider = (
        LocalModelProvider(fixtures_dir=settings.fixtures_dir)
        if settings.provider == "local"
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
    return report.model_dump(mode="json")


def _bedrock(settings: Settings) -> ModelProvider:
    from chronotrace.providers.bedrock import BedrockProvider

    return BedrockProvider(settings)
