"""The three-arm baseline sweep (spec 5).

The comparison the project's central claim rests on:

* **Arm A** — the model gets the test and the failure. No traces, no governor.
* **Arm B** — the same, plus the trace diff and ranked candidates. No governor.
* **Arm C** — the full ChronoTrace pipeline.

Arm B is the one people forget and the most informative, because it separates
what the trace evidence buys from what the policy gate buys. Either answer is
publishable; not knowing is the weak position.

**What is held constant.** Same model, temperature, seed, token cap, attempt
budget and per-run timeout. Capture and diagnosis run *once* per case and are
shared by all three arms, so no arm is compared against a luckier set of runs.
Verification is the same three tiers with the same forced ordering for every
arm. The only differences are the information supplied and the constraints
applied.

**Replay.** The captured evidence is recorded alongside the model calls, so a
replay reasons about the same traces the live run did. Without that the prompts
would differ between runs — they embed the observed flake rate and the captured
traceback — and a "replay" would silently be a different experiment.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chronotrace.capture.collect import collect
from chronotrace.config import Settings
from chronotrace.contracts import CaptureBundle, Diagnosis
from chronotrace.diagnose.depth import ConfirmationBudget
from chronotrace.diagnose.engine import diagnose
from chronotrace.errors import ProviderError
from chronotrace.eval.bandaid import BandAidScan, scan
from chronotrace.eval.baseline import BaselineOutcome, run_baseline
from chronotrace.eval.cases import BenchmarkCase
from chronotrace.logging import get_logger
from chronotrace.pipeline import repair
from chronotrace.providers.base import BaselineProvider

log = get_logger(__name__)

__all__ = ["ArmCaseResult", "SweepResult", "run_sweep"]

ARMS = ("A", "B", "C")


@dataclass
class ArmCaseResult:
    """One arm's result for one case."""

    arm: str
    case_id: str
    case_name: str
    is_control: bool
    expected_state: str
    """Ground-truth outcome. Fixes the metric denominators: the headline rates
    are over the 6 cases expected to be FIXED and the 5 negative controls, not
    over every case that happens to be in the corpus."""
    ui_state: str
    verified_repair: bool
    band_aid: BandAidScan
    modified_file: bool
    sleep_seconds: float
    tokens_input: int
    tokens_output: int
    model_calls: int
    attempts_used: int
    wall_clock_s: float
    tier_reached: str | None = None
    abstain_reason: str | None = None
    governor_rejected: bool = False
    failure_reason: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """Primitive-JSON view for the results file."""
        return {
            "arm": self.arm,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "is_control": self.is_control,
            "expected_state": self.expected_state,
            "ui_state": self.ui_state,
            "verified_repair": self.verified_repair,
            "band_aid": self.band_aid.is_band_aid,
            "band_aid_rules": self.band_aid.rule_ids,
            "band_aid_detail": self.band_aid.summary,
            "modified_file": self.modified_file,
            "sleep_seconds_added": self.sleep_seconds,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "model_calls": self.model_calls,
            "attempts_used": self.attempts_used,
            "wall_clock_s": self.wall_clock_s,
            "tier_reached": self.tier_reached,
            "abstain_reason": self.abstain_reason,
            "governor_rejected": self.governor_rejected,
            "failure_reason": self.failure_reason,
            "notes": self.notes,
        }


@dataclass
class SweepResult:
    """Every arm-case combination, plus what was captured about the run itself."""

    model: str
    provider: str
    results: list[ArmCaseResult] = field(default_factory=list)
    case_flake_rates: dict[str, float] = field(default_factory=dict)
    case_diagnoses: dict[str, str] = field(default_factory=dict)
    started_at: float = 0.0
    wall_clock_s: float = 0.0
    intent_parse_failures: int = 0
    """Arm C cases lost to invalid RepairIntent JSON rather than to failed repair."""
    excluded_cases: dict[str, str] = field(default_factory=dict)
    """Cases that could not run, and why. A subset corpus must say it is one."""

    def for_arm(self, arm: str) -> list[ArmCaseResult]:
        """Every result belonging to one arm."""
        return [result for result in self.results if result.arm == arm]


def run_sweep(
    cases: list[BenchmarkCase],
    *,
    cwd: Path,
    provider: BaselineProvider,
    settings: Settings,
    capture_runs: int = 20,
    probe_runs: int = 0,
    model_label: str = "",
    evidence_dir: Path | None = None,
    replay: bool = False,
    arms: tuple[str, ...] = ARMS,
) -> SweepResult:
    """Run all three arms over every case.

    Args:
        cases: The benchmark cases to sweep.
        cwd: Repository root.
        provider: A provider exposing both ``propose`` and ``propose_patch``.
        settings: Runtime settings, identical for every arm.
        capture_runs: Capture budget per case, shared by the arms.
        probe_runs: Uninstrumented runs per case for the probe-effect delta.
        model_label: Model name and version, recorded in the results.
        evidence_dir: Where captured traces and diagnoses are recorded, so a
            replay reasons about the same evidence.
        replay: Load the recorded evidence instead of capturing afresh. Reusing
            recorded evidence is also how two models are compared on identical
            traces, diagnoses and prompts, so that the model is the only
            variable.
        arms: Which arms to run. Defaults to all three.

    Returns:
        The sweep result.

    """
    sweep = SweepResult(
        model=model_label or getattr(provider, "model", "unknown"),
        provider=getattr(provider, "name", "unknown"),
        started_at=time.time(),
    )
    overall = time.monotonic()

    for case in cases:
        log.info("sweep.case", case=case.case_id, name=case.name)
        try:
            bundle, diagnosis = _evidence(
                case,
                cwd=cwd,
                settings=settings,
                capture_runs=capture_runs,
                probe_runs=probe_runs,
                evidence_dir=evidence_dir,
                replay=replay,
            )
        except ProviderError as exc:
            # A replay must not capture fresh traces, so a case with no recording
            # cannot run -- but that is a reason to leave it out of the sweep, not
            # to discard every case already completed. Excluded cases are named in
            # the result so a reader can see the corpus is a subset.
            log.warning("sweep.case_excluded", case=case.case_id, reason=str(exc))
            sweep.excluded_cases[case.case_id] = str(exc)
            continue
        sweep.case_flake_rates[case.case_id] = round(bundle.natural_flake_rate, 3)
        sweep.case_diagnoses[case.case_id] = f"{diagnosis.status}" + (
            f"/{diagnosis.abstain_reason}" if diagnosis.abstain_reason else ""
        )

        for arm in arms:
            if arm in {"A", "B"}:
                sweep.results.append(
                    _run_baseline_arm(arm, case, bundle, diagnosis, provider, cwd, settings)
                )
            else:
                result, parse_failed = _run_chronotrace_arm(
                    case, bundle, diagnosis, provider, cwd, settings
                )
                sweep.intent_parse_failures += int(parse_failed)
                sweep.results.append(result)

    sweep.wall_clock_s = round(time.monotonic() - overall, 1)
    return sweep


def _evidence(
    case: BenchmarkCase,
    *,
    cwd: Path,
    settings: Settings,
    capture_runs: int,
    probe_runs: int,
    evidence_dir: Path | None,
    replay: bool,
) -> tuple[CaptureBundle, Diagnosis]:
    """Capture traces and diagnose, or load a recording of both."""
    path = (evidence_dir / f"{case.case_id}.json") if evidence_dir else None
    if replay:
        if path is None or not path.exists():
            raise ProviderError(
                f"no recorded evidence for {case.case_id}; a replay cannot capture "
                "fresh traces without changing the experiment"
            )
        payload = json.loads(path.read_text())
        return (
            CaptureBundle.model_validate(payload["bundle"]),
            Diagnosis.model_validate(payload["diagnosis"]),
        )
    bundle = collect(
        case.test_id,
        cwd=cwd,
        runs=capture_runs,
        timeout_s=settings.run_timeout_s,
        probe_runs=probe_runs,
    )
    diagnosis = diagnose(
        bundle,
        cwd=cwd,
        budget=ConfirmationBudget(),
        timeout_s=settings.run_timeout_s,
        gate_timeout_s=settings.gate_timeout_s,
        allow_production_repair=settings.allow_production_repair,
    )
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "bundle": bundle.model_dump(mode="json"),
                    "diagnosis": diagnosis.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
        )
    return bundle, diagnosis


def _run_baseline_arm(
    arm: str,
    case: BenchmarkCase,
    bundle: CaptureBundle,
    diagnosis: Diagnosis,
    provider: BaselineProvider,
    cwd: Path,
    settings: Settings,
) -> ArmCaseResult:
    outcome: BaselineOutcome = run_baseline(
        arm=arm,
        case=case,
        bundle=bundle,
        diagnosis=diagnosis,
        provider=provider,
        cwd=cwd,
        settings=settings,
    )
    report = outcome.report
    verification = report.verification
    return ArmCaseResult(
        arm=arm,
        case_id=case.case_id,
        case_name=case.name,
        is_control=case.is_control,
        expected_state=case.expected_ui_state,
        ui_state=report.ui_state,
        verified_repair=bool(verification and verification.causally_proven),
        band_aid=outcome.band_aid,
        modified_file=outcome.modified_file,
        sleep_seconds=outcome.band_aid.sleep_seconds,
        tokens_input=report.tokens_input,
        tokens_output=report.tokens_output,
        model_calls=report.llm_calls,
        attempts_used=outcome.attempts_used,
        wall_clock_s=outcome.wall_clock_s,
        tier_reached=verification.tier_reached if verification else None,
        failure_reason=outcome.failure_reason,
        notes=outcome.per_attempt,
    )


def _run_chronotrace_arm(
    case: BenchmarkCase,
    bundle: CaptureBundle,
    diagnosis: Diagnosis,
    provider: BaselineProvider,
    cwd: Path,
    settings: Settings,
) -> tuple[ArmCaseResult, bool]:
    started = time.monotonic()
    target = cwd / case.test_id.split("::")[0]
    original = target.read_text()
    before_tokens = _totals(provider)
    provider.context = {"arm": "C", "case": case.case_id, "attempt": "1"}

    parse_failed = False
    failure_reason = ""
    try:
        report = repair(
            case.test_id,
            cwd=cwd,
            provider=provider,
            settings=settings,
            apply=False,
            bundle=bundle,
            diagnosis=diagnosis,
        )
    except ProviderError as exc:
        parse_failed = True
        failure_reason = f"model could not emit a valid RepairIntent: {exc}"
        log.warning("sweep.intent_invalid", case=case.case_id, error=str(exc))
        from chronotrace.contracts import IncidentReport

        report = IncidentReport(
            incident_id=f"c-{case.case_id.lower()}",
            test_id=case.test_id,
            ui_state="NEEDS_INVESTIGATION",
            diagnosis=diagnosis,
            provider=getattr(provider, "name", "unknown"),
        )

    after_tokens = _totals(provider)
    patched = _reconstruct(original, report.unified_diff)
    band_aid = scan(original, patched) if patched else BandAidScan()
    verification = report.verification
    return (
        ArmCaseResult(
            arm="C",
            case_id=case.case_id,
            case_name=case.name,
            is_control=case.is_control,
            expected_state=case.expected_ui_state,
            ui_state=report.ui_state,
            verified_repair=bool(verification and verification.causally_proven),
            band_aid=band_aid,
            modified_file=bool(report.unified_diff),
            sleep_seconds=band_aid.sleep_seconds,
            tokens_input=after_tokens[0] - before_tokens[0],
            tokens_output=after_tokens[1] - before_tokens[1],
            model_calls=report.llm_calls,
            attempts_used=1,
            wall_clock_s=round(time.monotonic() - started, 2),
            tier_reached=verification.tier_reached if verification else None,
            abstain_reason=report.diagnosis.abstain_reason,
            governor_rejected=bool(report.rejected_attempts),
            failure_reason=failure_reason,
        ),
        parse_failed,
    )


def _totals(provider: BaselineProvider) -> tuple[int, int]:
    totals = getattr(provider, "totals", None)
    return totals if isinstance(totals, tuple) else (0, 0)


def _reconstruct(original: str, diff: str | None) -> str | None:
    """Rebuild the patched source from a unified diff, for the band-aid scan.

    Arm C's report carries a diff rather than the patched file, because the
    patch is never written unless asked. Reconstructing it here keeps all three
    arms scanned by the same function on the same kind of input.
    """
    if not diff:
        return None
    lines = original.splitlines(keepends=True)
    result: list[str] = []
    index = 0
    for raw in diff.splitlines(keepends=True):
        if raw.startswith(("---", "+++")):
            continue
        if raw.startswith("@@"):
            header = raw.split("@@")[1].strip()
            old = header.split(" ")[0]
            start = int(old[1:].split(",")[0]) - 1
            result.extend(lines[index:start])
            index = start
            continue
        if raw.startswith("+"):
            result.append(raw[1:])
        elif raw.startswith("-"):
            index += 1
        elif raw.startswith(" "):
            result.append(lines[index] if index < len(lines) else raw[1:])
            index += 1
    result.extend(lines[index:])
    return "".join(result)
