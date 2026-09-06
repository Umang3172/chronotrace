"""Metric computation (spec 5, spec 19.5).

Repair rate alone is the wrong headline. For a system that modifies code, the
**false-repair rate matters more**: a patch that makes a non-race green is worse
than no patch, because it buries the real cause under a green build.

Every number here is computed from incident reports and ground truth. None of
them is entered by hand, and none is carried over from a different provider or a
different arm — a metric produced by one configuration says nothing about
another.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass, field

from chronotrace.contracts import IncidentReport
from chronotrace.eval.cases import BenchmarkCase
from chronotrace.govern.negative import check_negative

__all__ = ["ArmScore", "score_arm"]


@dataclass
class ArmScore:
    """Every metric for one experimental arm."""

    arm: str
    provider: str
    cases_run: int = 0

    supported_races: int = 0
    repaired: int = 0

    controls: int = 0
    false_repairs: int = 0
    correct_abstentions: int = 0
    abstention_expected: int = 0

    candidates_forced: int = 0
    candidates_causal: int = 0

    band_aid_patches: int = 0
    patches_produced: int = 0

    tokens_input: int = 0
    tokens_output: int = 0
    llm_calls: int = 0

    tier_counts: Counter[str] = field(default_factory=Counter)
    overheads_ms: list[float] = field(default_factory=list)
    wall_clock_s: float = 0.0
    ground_truth_matches: int = 0
    ground_truth_checked: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def repair_rate(self) -> float | None:
        """Fraction of supported races repaired and verified."""
        return self.repaired / self.supported_races if self.supported_races else None

    @property
    def false_repair_rate(self) -> float | None:
        """Fraction of negative controls that received a patch. Target zero."""
        return self.false_repairs / self.controls if self.controls else None

    @property
    def abstention_accuracy(self) -> float | None:
        """Fraction of cases that should abstain where the right refusal was given."""
        if not self.abstention_expected:
            return None
        return self.correct_abstentions / self.abstention_expected

    @property
    def causal_precision(self) -> float | None:
        """Fraction of forced candidates that reproduced the failure (spec 19.5)."""
        if not self.candidates_forced:
            return None
        return self.candidates_causal / self.candidates_forced

    @property
    def band_aid_rate(self) -> float | None:
        """Fraction of produced patches containing a timing band-aid."""
        if not self.patches_produced:
            return None
        return self.band_aid_patches / self.patches_produced

    @property
    def tokens_per_repair(self) -> float | None:
        """Total tokens divided by successful repairs, or None when unmeasured."""
        total = self.tokens_input + self.tokens_output
        if not total or not self.repaired:
            return None
        return total / self.repaired

    @property
    def median_overhead_ms(self) -> float | None:
        """Median measured post-patch overhead. Never reported as zero by default."""
        if not self.overheads_ms:
            return None
        ordered = sorted(self.overheads_ms)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2


def score_arm(
    arm: str, provider: str, results: list[tuple[BenchmarkCase, IncidentReport]]
) -> ArmScore:
    """Compute every metric for one arm.

    Args:
        arm: Arm label, ``"A"``, ``"B"`` or ``"C"``.
        provider: Provider name the arm ran against; metrics never mix providers.
        results: Case/report pairs produced by that arm.

    Returns:
        The scored arm.

    """
    score = ArmScore(arm=arm, provider=provider, cases_run=len(results))
    for case, report in results:
        score.wall_clock_s += report.wall_clock_s
        score.tokens_input += report.tokens_input
        score.tokens_output += report.tokens_output
        score.llm_calls += report.llm_calls

        for candidate in report.diagnosis.candidates:
            if candidate.classification in {
                "CAUSALLY_SUFFICIENT",
                "NECESSARY_INSUFFICIENT",
                "IRRELEVANT",
            }:
                score.candidates_forced += 1
                if candidate.classification == "CAUSALLY_SUFFICIENT":
                    score.candidates_causal += 1

        patched = report.unified_diff is not None and report.ui_state == "FIXED"
        if patched:
            score.patches_produced += 1
            if _contains_band_aid(report.unified_diff or ""):
                score.band_aid_patches += 1

        if case.is_supported_race:
            score.supported_races += 1
            if report.ui_state == "FIXED" and _verified(report):
                score.repaired += 1
        if case.expected_ui_state in {"ABSTAINED", "NEEDS_INVESTIGATION"}:
            score.abstention_expected += 1
            if report.ui_state == case.expected_ui_state and _reason_matches(case, report):
                score.correct_abstentions += 1
        if case.is_control:
            score.controls += 1
            if patched:
                score.false_repairs += 1

        if case.expected_transformation:
            score.ground_truth_checked += 1
            if report.intent and report.intent.transformation == case.expected_transformation:
                score.ground_truth_matches += 1

        if report.verification is not None:
            score.tier_counts[report.verification.tier_reached] += 1
            if report.ui_state == "FIXED":
                score.overheads_ms.append(report.verification.measured_overhead_ms)
        else:
            score.tier_counts["NOT_REACHED"] += 1
    return score


def _verified(report: IncidentReport) -> bool:
    return report.verification is not None and report.verification.causally_proven


def _reason_matches(case: BenchmarkCase, report: IncidentReport) -> bool:
    if case.expected_abstain_reason is None:
        return True
    return report.diagnosis.abstain_reason == case.expected_abstain_reason


def _contains_band_aid(diff: str) -> bool:
    """Scan a diff's added lines for band-aid constructs.

    The scan reuses the governor's own rules rather than a second
    reimplementation, so the measurement and the gate can never disagree.
    """
    added = "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    if not added.strip():
        return False
    wrapped = "async def _chronotrace_scanned() -> None:\n" + "\n".join(
        f"    {line}" for line in added.splitlines()
    )
    for candidate in (added, wrapped):
        try:
            ast.parse(candidate)
        except SyntaxError:
            continue
        return bool(check_negative("", candidate))
    return False
