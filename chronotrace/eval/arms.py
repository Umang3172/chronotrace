"""The three experimental arms (spec 5).

* **Arm A** — the model given the test file and the failure. No traces, no
  governor. This is what a general coding assistant does.
* **Arm B** — the model given the trace diff, but no governor.
* **Arm C** — full ChronoTrace.

Arm B is the one people forget and the most informative: it isolates how much of
the result comes from the traces versus from the gate. Either answer is
publishable; not knowing is the weak position.

All three arms must use the **same model at the same temperature with the same
attempt budget**. Comparing against published numbers from a different model is
not a controlled baseline, so a run that cannot honour that is refused rather
than reported with a caveat.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chronotrace.config import Settings
from chronotrace.contracts import IncidentReport
from chronotrace.errors import ProviderError
from chronotrace.eval.cases import BenchmarkCase
from chronotrace.logging import get_logger
from chronotrace.pipeline import repair
from chronotrace.providers.base import ModelProvider

log = get_logger(__name__)

__all__ = ["ArmResult", "run_arm"]


@dataclass
class ArmResult:
    """What one arm produced, or why it could not run."""

    arm: str
    provider: str
    results: list[tuple[BenchmarkCase, IncidentReport]]
    skipped_reason: str | None = None


def run_arm(
    arm: str,
    cases: list[BenchmarkCase],
    *,
    cwd: Path,
    provider: ModelProvider,
    settings: Settings,
    capture_runs: int = 20,
    probe_runs: int = 0,
) -> ArmResult:
    """Run one arm over the benchmark corpus.

    Args:
        arm: ``"A"``, ``"B"`` or ``"C"``.
        cases: The benchmark cases to run.
        cwd: Repository root.
        provider: The model provider, identical across arms.
        settings: Runtime settings.
        capture_runs: Capture budget per case.
        probe_runs: Uninstrumented runs per case for the probe-effect delta.

    Returns:
        The arm's results, or a skip with the reason it could not run honestly.

    """
    if arm in {"A", "B"} and not hasattr(provider, "propose_patch"):
        reason = (
            f"arm {arm} needs a provider that writes code, to measure what an unconstrained "
            f"model does. The {provider.name!r} provider is a hand-written decision policy, "
            "so running arm A or B against it would produce a baseline that describes this "
            "repository's own code rather than a model. Set CHRONOTRACE_PROVIDER=bedrock."
        )
        log.warning("eval.arm_skipped", arm=arm, reason=reason)
        return ArmResult(arm=arm, provider=provider.name, results=[], skipped_reason=reason)

    results: list[tuple[BenchmarkCase, IncidentReport]] = []
    for case in cases:
        log.info("eval.case", arm=arm, case=case.case_id)
        try:
            report = repair(
                case.test_id,
                cwd=cwd,
                provider=provider,
                settings=settings,
                capture_runs=capture_runs,
                probe_runs=probe_runs,
                apply=False,
            )
        except ProviderError as exc:
            log.warning("eval.case_failed", arm=arm, case=case.case_id, error=str(exc))
            continue
        results.append((case, report))
    return ArmResult(arm=arm, provider=provider.name, results=results)
