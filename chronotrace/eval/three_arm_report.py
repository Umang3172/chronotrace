"""Rendering for the three-arm baseline (spec 8).

Every figure here is computed from the sweep. Nothing is hand-entered, and a
metric that cannot be computed prints ``n/a`` rather than an estimate — a
cost-per-repair for an arm with zero repairs is undefined, not zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from chronotrace.eval.three_arm import ARMS, SweepResult

__all__ = ["ArmSummary", "render_table", "summarise_arm", "write_results"]

RUNS_PER_DAY = 50
DAYS_PER_YEAR = 365


@dataclass
class ArmSummary:
    """Computed metrics for one arm."""

    arm: str
    repairable_cases: int = 0
    verified_repairs: int = 0
    band_aids: int = 0
    band_aid_cases: list[tuple[str, str]] = field(default_factory=list)
    other_cases: int = 0
    """Cases that are neither a repairable race nor a control (depth-2,
    production-scope, over-constrained assertion). Reported separately."""
    controls: int = 0
    false_repairs: int = 0
    false_repair_cases: list[str] = field(default_factory=list)
    sleep_seconds: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    model_calls: int = 0
    wall_clock_s: float = 0.0
    forced_tier_cases: int = 0
    unusable_outputs: int = 0

    @property
    def tokens_total(self) -> int:
        """Input plus output tokens across the arm."""
        return self.tokens_input + self.tokens_output

    @property
    def tokens_per_repair(self) -> float | None:
        """Tokens per *verified* repair, or None when there were none."""
        if self.verified_repairs == 0:
            return None
        return self.tokens_total / self.verified_repairs

    @property
    def annual_ci_hours(self) -> float:
        """Hours of CI time per year the injected delays would cost."""
        return self.sleep_seconds * RUNS_PER_DAY * DAYS_PER_YEAR / 3600.0


def summarise_arm(sweep: SweepResult, arm: str) -> ArmSummary:
    """Compute every metric for one arm."""
    summary = ArmSummary(arm=arm)
    for result in sweep.for_arm(arm):
        summary.wall_clock_s += result.wall_clock_s
        summary.tokens_input += result.tokens_input
        summary.tokens_output += result.tokens_output
        summary.model_calls += result.model_calls
        if result.failure_reason:
            summary.unusable_outputs += 1
        if result.is_control:
            summary.controls += 1
            if result.modified_file:
                summary.false_repairs += 1
                summary.false_repair_cases.append(result.case_id)
            continue
        if result.expected_state != "FIXED":
            summary.other_cases += 1
            continue
        summary.repairable_cases += 1
        if result.verified_repair:
            summary.verified_repairs += 1
        if result.tier_reached == "FORCED" and result.verified_repair:
            summary.forced_tier_cases += 1
        if result.band_aid.is_band_aid:
            summary.band_aids += 1
            summary.band_aid_cases.append((result.case_id, result.band_aid.summary))
        summary.sleep_seconds += max(0.0, result.sleep_seconds)
    return summary


def _causality(summary: ArmSummary, arm: str) -> str:
    if arm in {"A", "B"}:
        return "no"
    if summary.forced_tier_cases == 0:
        return "no"
    return f"yes — {summary.forced_tier_cases}/{summary.repairable_cases} at forced tier"


def render_table(summaries: dict[str, ArmSummary]) -> str:
    """Render the comparison table and its supporting detail."""
    a, b, c = (summaries[arm] for arm in ARMS)
    repairable = max(a.repairable_cases, b.repairable_cases, c.repairable_cases)
    controls = max(a.controls, b.controls, c.controls)

    def tokens(summary: ArmSummary) -> str:
        value = summary.tokens_per_repair
        if value is None:
            return f"undefined ({summary.tokens_total:,} tokens, 0 repairs)"
        return f"{value:,.0f}"

    def ci_seconds(summary: ArmSummary) -> str:
        return "0 s" if summary.sleep_seconds == 0 else f"{summary.sleep_seconds:g} s"

    def annual(summary: ArmSummary) -> str:
        if summary.sleep_seconds == 0:
            return "0 h"
        return f"{summary.annual_ci_hours:,.1f} h"

    rows = [
        (
            "Races repaired (verified)",
            *(f"{s.verified_repairs} / {repairable}" for s in (a, b, c)),
        ),
        (
            "**Band-aids injected**",
            *(f"**{s.band_aids} / {repairable}**" for s in (a, b, c)),
        ),
        ("CI seconds added per run", *(ci_seconds(s) for s in (a, b, c))),
        ("Projected annual CI cost (50 runs/day)", *(annual(s) for s in (a, b, c))),
        (
            "False repairs on 5 controls",
            *(f"{s.false_repairs} / {controls}" for s in (a, b, c)),
        ),
        ("Tokens per successful repair", *(tokens(s) for s in (a, b, c))),
        ("Causality proven", *(_causality(s, arm) for s, arm in zip((a, b, c), ARMS, strict=True))),
    ]

    lines = [
        "| Metric | Arm A (code only) | Arm B (+ traces) | Arm C (ChronoTrace) |",
        "|---|---|---|---|",
    ]
    lines += [f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |" for row in rows]
    return "\n".join(lines)


def render_detail(sweep: SweepResult, summaries: dict[str, ArmSummary]) -> str:
    """Render the per-case breakdown that sits below the table."""
    lines: list[str] = []
    lines.append(
        f"Local-model baseline: **{sweep.model}** via `{sweep.provider}`, "
        f"{len(sweep.for_arm('A'))} cases per arm "
        f"({summaries['A'].repairable_cases} repairable races, "
        f"{summaries['A'].controls} negative controls), "
        f"{sweep.wall_clock_s / 60:.0f} min wall clock."
    )
    lines.append(
        "These are **local-model numbers, not the submission numbers.** A Bedrock "
        "re-run against a larger model is planned, and those figures are the ones "
        "that will be quoted in the submission. A small quantised local model is a "
        "weak stand-in for what a developer would actually have pointed at this "
        "problem, in both directions: it may reach for cruder fixes than a frontier "
        "model would, and it may also fail to produce a usable patch at all."
    )

    for arm in ("A", "B"):
        summary = summaries[arm]
        lines.append(f"\n### Arm {arm} — per case\n")
        lines.append("| Case | Patch | Band-aid pattern |")
        lines.append("|---|---|---|")
        for result in sweep.for_arm(arm):
            if result.is_control:
                continue
            patch = (
                "no usable output"
                if result.failure_reason
                else ("modified" if result.modified_file else "unchanged")
            )
            detail = result.band_aid.summary if result.band_aid.is_band_aid else "none"
            lines.append(f"| {result.case_id} {result.case_name} | {patch} | {detail} |")
        if summary.unusable_outputs:
            lines.append(
                f"\n{summary.unusable_outputs} of {len(sweep.for_arm(arm))} cases produced "
                "no usable patch within the attempt budget."
            )

    lines.append("\n### Arm C — abstention on the negative controls\n")
    lines.append("| Case | State | Reason |")
    lines.append("|---|---|---|")
    for result in sweep.for_arm("C"):
        if not result.is_control:
            continue
        lines.append(
            f"| {result.case_id} {result.case_name} | {result.ui_state} | "
            f"{result.abstain_reason or '—'} |"
        )

    if sweep.intent_parse_failures:
        lines.append(
            f"\n**{sweep.intent_parse_failures} Arm C cases were lost to invalid "
            "`RepairIntent` JSON**, which is a model capability limit rather than a "
            "ChronoTrace result. Those cases are excluded from any claim about repair "
            "quality."
        )
    return "\n".join(lines)


def write_results(
    sweep: SweepResult, out_dir: Path, *, extra: dict[str, object] | None = None
) -> tuple[Path, Path]:
    """Write the JSON results and the markdown table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = {arm: summarise_arm(sweep, arm) for arm in ARMS}
    table = render_table(summaries)
    detail = render_detail(sweep, summaries)

    markdown_path = out_dir / "three_arm_table.md"
    markdown_path.write_text(f"{table}\n\n{detail}\n")

    payload: dict[str, object] = {
        "model": sweep.model,
        "provider": sweep.provider,
        "started_at": sweep.started_at,
        "wall_clock_s": sweep.wall_clock_s,
        "intent_parse_failures": sweep.intent_parse_failures,
        "case_flake_rates": sweep.case_flake_rates,
        "case_diagnoses": sweep.case_diagnoses,
        "summaries": {
            arm: {
                "repairable_cases": s.repairable_cases,
                "other_cases": s.other_cases,
                "verified_repairs": s.verified_repairs,
                "band_aids": s.band_aids,
                "band_aid_cases": s.band_aid_cases,
                "controls": s.controls,
                "false_repairs": s.false_repairs,
                "false_repair_cases": s.false_repair_cases,
                "sleep_seconds_per_run": s.sleep_seconds,
                "annual_ci_hours_at_50_runs_per_day": s.annual_ci_hours,
                "tokens_input": s.tokens_input,
                "tokens_output": s.tokens_output,
                "tokens_per_verified_repair": s.tokens_per_repair,
                "model_calls": s.model_calls,
                "wall_clock_s": s.wall_clock_s,
                "forced_tier_cases": s.forced_tier_cases,
                "unusable_outputs": s.unusable_outputs,
            }
            for arm, s in summaries.items()
        },
        "results": [result.to_json() for result in sweep.results],
    }
    if extra:
        payload.update(extra)
    json_path = out_dir / "three_arm_ollama_qwen3_8b.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return json_path, markdown_path
