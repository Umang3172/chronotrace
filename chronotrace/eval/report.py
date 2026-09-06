"""Results rendering — one command produces every number in the README (A-5).

Nothing in the README, the deck or the video may be hand-entered. If this script
did not produce it, it does not get claimed. Metrics that were not measured are
printed as ``n/a`` with the reason, because an absent number is honest and an
invented one is not.
"""

from __future__ import annotations

import json
from pathlib import Path

from chronotrace.eval.arms import ArmResult
from chronotrace.eval.score import ArmScore, score_arm

__all__ = ["render_markdown", "summarise", "write_report"]

_ARM_LABELS = {
    "A": "model only, no traces and no governor",
    "B": "model with the trace diff, no governor",
    "C": "full ChronoTrace",
}


def summarise(arms: list[ArmResult]) -> list[ArmScore]:
    """Score every arm that ran."""
    return [score_arm(arm.arm, arm.provider, arm.results) for arm in arms if arm.results]


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _number(value: float | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:g}{suffix}"


def render_markdown(arms: list[ArmResult], scores: list[ArmScore]) -> str:
    """Render the results table and the honesty notes that belong with it."""
    lines: list[str] = []
    lines.append("## Results\n")
    lines.append(
        "Seeded benchmark, produced by `chronotrace eval`. N is small and the corpus is "
        "seeded rather than mined from the wild, so this is a controlled comparison "
        "between arms on identical inputs — a directional effect, not a population "
        "estimate.\n"
    )
    header = "| Metric | " + " | ".join(f"Arm {score.arm}" for score in scores) + " |"
    divider = "|---|" + "---|" * len(scores)
    lines.append(header)
    lines.append(divider)

    rows: list[tuple[str, list[str]]] = [
        ("Cases run", [str(score.cases_run) for score in scores]),
        (
            "Repair rate on supported races",
            [
                f"{_percent(score.repair_rate)} ({score.repaired}/{score.supported_races})"
                for score in scores
            ],
        ),
        (
            "**False-repair rate on controls**",
            [
                f"{_percent(score.false_repair_rate)} ({score.false_repairs}/{score.controls})"
                for score in scores
            ],
        ),
        (
            "Abstention accuracy",
            [
                f"{_percent(score.abstention_accuracy)} "
                f"({score.correct_abstentions}/{score.abstention_expected})"
                for score in scores
            ],
        ),
        (
            "Causal precision",
            [
                f"{_percent(score.causal_precision)} "
                f"({score.candidates_causal}/{score.candidates_forced})"
                for score in scores
            ],
        ),
        (
            "**Band-aid injection rate**",
            [
                f"{_percent(score.band_aid_rate)} "
                f"({score.band_aid_patches}/{score.patches_produced})"
                for score in scores
            ],
        ),
        (
            "Ground-truth transformation match",
            [f"{score.ground_truth_matches}/{score.ground_truth_checked}" for score in scores],
        ),
        (
            "Median measured overhead",
            [_number(score.median_overhead_ms, " ms") for score in scores],
        ),
        ("Model calls", [str(score.llm_calls) for score in scores]),
        (
            "Tokens per successful repair",
            [_number(score.tokens_per_repair) for score in scores],
        ),
        (
            "Wall clock",
            [f"{score.wall_clock_s:.0f} s" for score in scores],
        ),
        (
            "Verification tiers reached",
            [
                ", ".join(f"{tier} x{count}" for tier, count in sorted(score.tier_counts.items()))
                or "n/a"
                for score in scores
            ],
        ),
    ]
    for label, values in rows:
        lines.append(f"| {label} | " + " | ".join(values) + " |")

    lines.append("")
    for score in scores:
        lines.append(
            f"- **Arm {score.arm}** — {_ARM_LABELS.get(score.arm, '')}, "
            f"provider `{score.provider}`."
        )
    for arm in arms:
        if arm.skipped_reason:
            lines.append(f"- **Arm {arm.arm} did not run.** {arm.skipped_reason}")
    if any(score.tokens_per_repair is None for score in scores):
        lines.append(
            "- Token and cost figures are reported only for providers that return usage. "
            "The local reference policy is not a model and has no tokens to report; "
            "inventing a number there would be a fabricated metric."
        )
    lines.append(
        "- Overhead is a measured median delta in test-call duration, natural runs before "
        "versus after the patch. ChronoTrace never claims zero added cost: a "
        "synchronization primitive changes scheduling even when it adds no fixed delay. "
        "The claim is *no fixed sleep-based delay introduced*, plus this number."
    )
    return "\n".join(lines) + "\n"


def write_report(arms: list[ArmResult], out_dir: Path) -> tuple[Path, Path]:
    """Write the markdown table and the raw JSON, returning both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scores = summarise(arms)
    markdown = render_markdown(arms, scores)
    markdown_path = out_dir / "results.md"
    markdown_path.write_text(markdown)
    payload = {
        "arms": [
            {
                "arm": arm.arm,
                "provider": arm.provider,
                "skipped_reason": arm.skipped_reason,
                "cases": [
                    {"case": case.case_id, "report": report.model_dump(mode="json")}
                    for case, report in arm.results
                ],
            }
            for arm in arms
        ],
        "scores": [
            {
                "arm": score.arm,
                "provider": score.provider,
                "cases_run": score.cases_run,
                "repair_rate": score.repair_rate,
                "false_repair_rate": score.false_repair_rate,
                "abstention_accuracy": score.abstention_accuracy,
                "causal_precision": score.causal_precision,
                "band_aid_rate": score.band_aid_rate,
                "tokens_per_repair": score.tokens_per_repair,
                "median_overhead_ms": score.median_overhead_ms,
                "tier_counts": dict(score.tier_counts),
                "ground_truth_matches": score.ground_truth_matches,
                "ground_truth_checked": score.ground_truth_checked,
            }
            for score in scores
        ],
    }
    json_path = out_dir / "results.json"
    json_path.write_text(json.dumps(payload, indent=2))
    return markdown_path, json_path
