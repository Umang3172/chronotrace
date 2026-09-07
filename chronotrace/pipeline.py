"""End-to-end repair pipeline.

The order of stages is the safety argument. Capture gathers evidence; diagnosis
decides whether there is anything to prove and proves it by forcing; the model
selects a pattern and emits a typed intent; deterministic code applies it; the
governor decides whether it may run at all; verification decides whether it
worked. The thing that decides is never the thing that verifies.

Nothing here writes to the repository unless explicitly asked. The output is a
diff and a report; a human merges.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Literal

from chronotrace.capture.collect import collect
from chronotrace.config import Settings
from chronotrace.contracts import (
    CaptureBundle,
    Diagnosis,
    IncidentReport,
    LaneSpan,
    TraceCapture,
    TraceLane,
)
from chronotrace.diagnose.depth import ConfirmationBudget
from chronotrace.diagnose.engine import diagnose
from chronotrace.errors import PatchError
from chronotrace.govern import gate
from chronotrace.logging import get_logger
from chronotrace.providers.base import ModelProvider
from chronotrace.synthesize.apply import apply_intent, unified_diff
from chronotrace.verify import regression, tiers
from chronotrace.verify.runner import run_test

log = get_logger(__name__)

__all__ = ["repair"]


def repair(
    test_id: str,
    *,
    cwd: Path,
    provider: ModelProvider,
    settings: Settings,
    capture_runs: int = 30,
    probe_runs: int = 0,
    apply: bool = False,
    bundle: CaptureBundle | None = None,
    diagnosis: Diagnosis | None = None,
) -> IncidentReport:
    """Run the full pipeline for one flaky test.

    Args:
        test_id: pytest node id of the flaky test.
        cwd: Repository root.
        provider: The model provider selecting the repair pattern.
        settings: Runtime settings.
        capture_runs: Budget for gathering a comparable pass/fail pair.
        probe_runs: Uninstrumented runs for the probe-effect measurement (D3).
        apply: Leave the patch on disk. Off by default — ChronoTrace proposes a
            diff, it does not write to your repository.
        bundle: Pre-captured traces. Supplied by the three-arm harness so every
            arm reasons about the identical execution evidence; captured here
            when omitted.
        diagnosis: Pre-computed diagnosis, for the same reason. Diagnosis is
            deterministic and involves no model call, so sharing it across arms
            changes nothing except that they are compared on the same evidence.

    Returns:
        The incident report, whatever the outcome.

    """
    started = time.monotonic()
    calls_before = provider.calls
    incident_id = uuid.uuid4().hex[:8]
    log.info("pipeline.start", incident=incident_id, test_id=test_id)

    if bundle is None:
        bundle = collect(
            test_id,
            cwd=cwd,
            runs=capture_runs,
            timeout_s=settings.run_timeout_s,
            probe_runs=probe_runs,
        )
    if diagnosis is None:
        diagnosis = diagnose(
            bundle,
            cwd=cwd,
            budget=ConfirmationBudget(),
            timeout_s=settings.run_timeout_s,
            gate_timeout_s=settings.gate_timeout_s,
            allow_production_repair=settings.allow_production_repair,
        )
    highlighted = _highlighted_keys(diagnosis)
    report = IncidentReport(
        incident_id=incident_id,
        test_id=test_id,
        ui_state=_state_for(diagnosis),
        diagnosis=diagnosis,
        provider=provider.name,
        natural_flake_rate=bundle.natural_flake_rate,
        probe_effect_delta=bundle.probe_effect_delta,
        pass_lane=_lane(bundle.passing[0], highlighted) if bundle.passing else None,
        fail_lane=_lane(bundle.failing[0], highlighted) if bundle.failing else None,
    )
    if diagnosis.status != "RACE_PROVEN" or diagnosis.proven_inversion is None:
        return _finish(report, started, provider, calls_before)

    inversion = diagnosis.proven_inversion
    target = cwd / inversion.op_a.source_file
    if not target.is_absolute():
        target = Path(inversion.op_a.source_file)
    source = target.read_text()

    intent = provider.propose(diagnosis, source)
    report.intent = intent
    if intent.transformation in {"NO_REPAIR", "RELAX_ASSERTION"}:
        report.ui_state = "NEEDS_INVESTIGATION"
        return _finish(report, started, provider, calls_before)

    try:
        patch = apply_intent(
            source,
            intent,
            path=str(target.relative_to(cwd)) if target.is_absolute() else str(target),
            is_test_module=inversion.op_a.is_test_scope,
        )
    except PatchError as exc:
        log.warning("pipeline.patch_failed", incident=incident_id, error=str(exc))
        report.ui_state = "NEEDS_INVESTIGATION"
        report.diagnosis.explanation += f" No patch could be applied: {exc}"
        return _finish(report, started, provider, calls_before)

    verdict = gate.review(
        before=patch.original,
        after=patch.patched,
        path=patch.path,
        allow_production_repair=settings.allow_production_repair,
    )
    report.verdict = verdict
    if not verdict.approved:
        report.rejected_attempts.append(verdict)
        report.ui_state = "NEEDS_INVESTIGATION"
        return _finish(report, started, provider, calls_before)

    guarded = regression.append_regression_test(
        patch.patched,
        test_function=test_id.split("::")[-1],
        forced_order=inversion.failing_order,
        incident_id=incident_id,
        natural_flake_rate=bundle.natural_flake_rate,
        gate_timeout_s=settings.gate_timeout_s,
    )
    report.unified_diff = unified_diff(patch.original, guarded, patch.path)

    verification = tiers.verify(
        test_id=test_id,
        cwd=cwd,
        target=target,
        patched_source=guarded,
        forced_order=inversion.failing_order,
        timeout_s=settings.run_timeout_s,
        gate_timeout_s=settings.gate_timeout_s,
        statistical_runs=settings.statistical_runs,
        pct_runs=settings.pct_runs,
        isolation=settings.isolation,
    )
    report.verification = verification

    guard_name = regression.regression_test_name(incident_id)
    guard_id = f"{test_id.split('::')[0]}::{guard_name}"
    if verification.causally_proven:
        with tiers.patched_file(target, guarded):
            outcome = run_test(guard_id, cwd=cwd, timeout_s=settings.run_timeout_s, seed=None)
        report.regression_verified = outcome.passed and outcome.collected
        report.regression_test_path = guard_id

    if verification.deadlock_detected:
        report.ui_state = "NEEDS_INVESTIGATION"
        report.diagnosis.explanation += (
            " Verification timed out after the patch was applied, which is a deadlock "
            "signal. The patch was rolled back."
        )
    elif verification.causally_proven and report.regression_verified:
        report.ui_state = "FIXED"
        if apply:
            target.write_text(guarded)
            log.info("pipeline.applied", incident=incident_id, path=str(target))
    else:
        report.ui_state = "NEEDS_INVESTIGATION"

    return _finish(report, started, provider, calls_before)


def _highlighted_keys(diagnosis: Diagnosis) -> set[str]:
    """Operation keys to outline in the divergence view."""
    inversion = diagnosis.proven_inversion or (
        diagnosis.candidates[0] if diagnosis.candidates else None
    )
    return set(inversion.failing_order) if inversion else set()


def _lane(capture: TraceCapture, highlighted: set[str]) -> TraceLane:
    """Place one execution's spans on a relative millisecond axis."""
    if not capture.spans:
        return TraceLane(outcome=capture.outcome, run_id=capture.run_id, total_ms=0.0)
    origin = min(span.start_ns for span in capture.spans)
    end = max(span.end_ns for span in capture.spans)
    spans = [
        LaneSpan(
            key=span.key,
            name=span.name,
            start_ms=round((span.start_ns - origin) / 1e6, 4),
            duration_ms=round((span.end_ns - span.start_ns) / 1e6, 4),
            task_name=span.task_name,
            source_line=span.source_line,
            access=(str(span.attributes["ct.access"]) if "ct.access" in span.attributes else None),
            in_inversion=span.key in highlighted,
            is_assertion=bool(span.attributes.get("ct.assertion")),
        )
        for span in sorted(capture.spans, key=lambda item: item.start_ns)
    ]
    return TraceLane(
        outcome=capture.outcome,
        run_id=capture.run_id,
        total_ms=round((end - origin) / 1e6, 4),
        spans=spans,
    )


def _state_for(diagnosis: Diagnosis) -> Literal["FIXED", "NEEDS_INVESTIGATION", "ABSTAINED"]:
    """Return the initial UI state from the diagnosis alone.

    A proven race is still only NEEDS_INVESTIGATION here: FIXED is earned later,
    by a patch that passes the gate and is verified, never by a diagnosis.
    """
    if diagnosis.status == "ABSTAINED":
        return "ABSTAINED"
    return "NEEDS_INVESTIGATION"


def _finish(
    report: IncidentReport,
    started: float,
    provider: ModelProvider,
    calls_before: int,
) -> IncidentReport:
    tokens_in, tokens_out = provider.last_usage
    report.tokens_input = tokens_in
    report.tokens_output = tokens_out
    # Calls made for *this* incident. ``provider.calls`` is cumulative across the
    # provider's lifetime, so reporting it directly inflates every incident after
    # the first when one provider serves a whole sweep.
    report.llm_calls = provider.calls - calls_before
    report.wall_clock_s = round(time.monotonic() - started, 2)
    log.info(
        "pipeline.done",
        incident=report.incident_id,
        state=report.ui_state,
        tier=report.verification.tier_reached if report.verification else None,
    )
    return report
