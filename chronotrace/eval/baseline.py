"""Arms A and B — what a model does when nothing stops it.

These arms exist to measure the counterfactual, so they are deliberately
unconstrained: the model is asked to fix a failing test, and whatever source it
returns is written to disk verbatim. No typed intent, no policy gate, no LibCST.

Fairness is the whole point, so everything except the *information supplied* is
held identical to Arm C: same model, temperature, seed, token cap, attempt
budget and per-run timeout, the same captured traces, and the same three-tier
verification with the same forced ordering. The forced ordering used to verify
Arms A and B comes from ChronoTrace's own diagnosis — the baseline model never
sees it, but the *verifier* must, or the arms would be judged by different
standards.

Two accommodations are made in the baseline's favour, both deliberate: markdown
fences are stripped from the response before applying it, and a response that
does not parse as Python costs an attempt rather than the case.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from chronotrace.config import Settings
from chronotrace.contracts import CaptureBundle, Diagnosis, IncidentReport
from chronotrace.errors import ProviderError
from chronotrace.eval.bandaid import BandAidScan, scan
from chronotrace.eval.cases import BenchmarkCase
from chronotrace.logging import get_logger
from chronotrace.providers.base import BaselineProvider
from chronotrace.synthesize.apply import unified_diff
from chronotrace.verify import tiers

log = get_logger(__name__)

__all__ = ["ARM_A_HINT", "ARM_B_HINT", "BaselineOutcome", "run_baseline"]

ARM_A_HINT = ""
"""Arm A gets no addition to the system prompt. Any nudge would invalidate it."""

ARM_B_HINT = ""
"""Arm B gets evidence in the user prompt, not guidance in the system prompt."""

_FENCE = re.compile(r"^\s*```(?:python|py)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


@dataclass
class BaselineOutcome:
    """Everything one baseline arm produced for one case."""

    case_id: str
    arm: str
    report: IncidentReport
    band_aid: BandAidScan
    attempts_used: int
    usable_patch: bool
    modified_file: bool
    wall_clock_s: float
    prompt_chars: int = 0
    failure_reason: str = ""
    per_attempt: list[str] = field(default_factory=list)


def strip_fences(text: str) -> str:
    """Remove a markdown code fence if the model wrapped the file in one."""
    match = _FENCE.match(text.strip())
    return match.group(1) if match else text.strip()


def _failure_excerpt(bundle: CaptureBundle, limit: int = 1800) -> str:
    for capture in bundle.failing:
        if capture.failure_message:
            return capture.failure_message[-limit:]
    return "(no traceback captured)"


def _trace_evidence(bundle: CaptureBundle, diagnosis: Diagnosis) -> str:
    """Render the trace diff and ranked candidates for Arm B.

    Evidence only. No instruction about what to do with it, and no forced-replay
    result — that belongs to Arm C's diagnosis, not to the trace diff.
    """
    lines: list[str] = []
    if bundle.passing:
        passing = bundle.passing[0]
        order = " -> ".join(span.key for span in sorted(passing.spans, key=lambda s: s.start_ns))
        lines.append(f"Operation order in a passing run:\n  {order or '(no operations)'}")
    if bundle.failing:
        failing = bundle.failing[0]
        order = " -> ".join(span.key for span in sorted(failing.spans, key=lambda s: s.start_ns))
        lines.append(f"Operation order in a failing run:\n  {order or '(no operations)'}")
        pass_names = {span.name for capture in bundle.passing for span in capture.spans}
        fail_names = {span.name for span in failing.spans}
        missing = sorted(pass_names - fail_names)
        if missing:
            lines.append(
                "Operations seen in passing runs but never started in the failing run:\n  "
                + ", ".join(missing)
            )
    lines.append(
        f"Observed across {len(bundle.passing)} passing and {len(bundle.failing)} failing runs."
    )
    if diagnosis.candidates:
        ranked = "\n".join(
            f"  {index}. {' before '.join(c.failing_order)}"
            f"   suspiciousness {c.ochiai_score:.2f}"
            + ("   (the failed assertion depends on these)" if c.in_backward_slice else "")
            for index, c in enumerate(diagnosis.candidates, start=1)
        )
        lines.append(
            "Candidate ordering differences between passing and failing runs, ranked by "
            "how strongly each is associated with failure (1.00 = present in every "
            f"failing run and no passing run):\n{ranked}"
        )
        top = diagnosis.candidates[0]
        lines.append(
            "Identified inverted operation pair:\n  "
            f"{top.failing_order[0]} starts before {top.failing_order[1]} when the test "
            "fails, and after it when the test passes."
        )
    else:
        lines.append(
            "No ordering difference was found between the passing and failing runs: "
            "both executed the same operations in the same order."
        )
    return "\n\n".join(lines)


def build_prompt(
    arm: str, case: BenchmarkCase, source: str, bundle: CaptureBundle, diagnosis: Diagnosis
) -> str:
    """Build the user prompt for a baseline arm.

    Arm A is a neutral request of the kind a developer would actually write. It
    must not mention sleeps, synchronization, or anything else that would tell
    the model what a good answer looks like.
    """
    path = case.test_id.split("::")[0]
    failures = len(bundle.failing)
    executed = max(1, bundle.runs_executed - bundle.runs_timed_out)
    prompt = f"""This test fails intermittently. It failed {failures} of {executed} runs.

File: {path}

```python
{source}```

Output from a failing run:

{_failure_excerpt(bundle)}
"""
    if arm == "B":
        prompt += f"""
Execution traces were captured from both passing and failing runs. Here is what
they show:

{_trace_evidence(bundle, diagnosis)}
"""
    prompt += "\nFix it. Return the complete corrected contents of the file."
    return prompt


def run_baseline(
    *,
    arm: str,
    case: BenchmarkCase,
    bundle: CaptureBundle,
    diagnosis: Diagnosis,
    provider: BaselineProvider,
    cwd: Path,
    settings: Settings,
) -> BaselineOutcome:
    """Run one baseline arm against one case.

    Args:
        arm: ``"A"`` or ``"B"``.
        case: The benchmark case.
        bundle: Captured traces, shared with every other arm for this case.
        diagnosis: ChronoTrace's diagnosis, used for verification only. Arm A
            never sees it; Arm B sees the trace diff and candidates from it.
        provider: A provider exposing ``propose_patch``.
        cwd: Repository root.
        settings: Runtime settings.

    Returns:
        The outcome, including the band-aid scan and the verification result.

    """
    started = time.monotonic()
    target = cwd / case.test_id.split("::")[0]
    original = target.read_text()
    prompt = build_prompt(arm, case, original, bundle, diagnosis)

    patched: str | None = None
    attempts = 0
    notes: list[str] = []
    max_attempts = settings.max_attempts
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        provider.context = {"arm": arm, "case": case.case_id, "attempt": str(attempt)}
        try:
            raw = provider.propose_patch(
                system_extra=ARM_A_HINT if arm == "A" else ARM_B_HINT, user=prompt
            )
        except ProviderError as exc:
            notes.append(f"attempt {attempt}: provider error: {exc}")
            continue
        candidate = strip_fences(raw)
        result = scan(original, candidate)
        if result.parse_error is not None:
            notes.append(f"attempt {attempt}: response did not parse ({result.parse_error})")
            continue
        patched = candidate
        notes.append(f"attempt {attempt}: usable patch")
        break

    report = IncidentReport(
        incident_id=f"{arm.lower()}-{case.case_id.lower()}",
        test_id=case.test_id,
        ui_state="NEEDS_INVESTIGATION",
        diagnosis=Diagnosis(
            status="NEEDS_INVESTIGATION",
            explanation=f"Arm {arm} baseline: the model rewrote the file directly.",
        ),
        provider=getattr(provider, "name", "unknown"),
        natural_flake_rate=bundle.natural_flake_rate,
        probe_effect_delta=bundle.probe_effect_delta,
    )
    if patched is None:
        # Attempts that produced nothing usable still cost tokens. Recording them
        # keeps the baseline's true cost visible rather than quietly free.
        tokens_in, tokens_out = provider.last_usage
        report.tokens_input, report.tokens_output = tokens_in, tokens_out
        report.llm_calls = attempts
        report.wall_clock_s = round(time.monotonic() - started, 2)
        return BaselineOutcome(
            case_id=case.case_id,
            arm=arm,
            report=report,
            band_aid=BandAidScan(parse_error="no usable patch produced"),
            attempts_used=attempts,
            usable_patch=False,
            modified_file=False,
            wall_clock_s=report.wall_clock_s,
            prompt_chars=len(prompt),
            failure_reason="no usable patch after the attempt budget",
            per_attempt=notes,
        )

    band_aid = scan(original, patched)
    modified = patched.strip() != original.strip()
    report.unified_diff = unified_diff(original, patched, str(target.relative_to(cwd)))

    forced_order = diagnosis.proven_inversion.failing_order if diagnosis.proven_inversion else None
    if modified and forced_order:
        report.verification = tiers.verify(
            test_id=case.test_id,
            cwd=cwd,
            target=target,
            patched_source=patched,
            forced_order=forced_order,
            timeout_s=settings.run_timeout_s,
            gate_timeout_s=settings.gate_timeout_s,
            statistical_runs=settings.statistical_runs,
            pct_runs=settings.pct_runs,
            isolation=settings.isolation,
        )
        if report.verification.causally_proven:
            report.ui_state = "FIXED"
    report.wall_clock_s = round(time.monotonic() - started, 2)
    tokens_in, tokens_out = provider.last_usage
    report.tokens_input, report.tokens_output = tokens_in, tokens_out
    report.llm_calls = attempts
    log.info(
        "baseline.done",
        arm=arm,
        case=case.case_id,
        band_aid=band_aid.rule_ids,
        state=report.ui_state,
    )
    return BaselineOutcome(
        case_id=case.case_id,
        arm=arm,
        report=report,
        band_aid=band_aid,
        attempts_used=attempts,
        usable_patch=True,
        modified_file=modified,
        wall_clock_s=report.wall_clock_s,
        prompt_chars=len(prompt),
        per_attempt=notes,
    )
