"""Replay verification for the three-arm sweep (spec 6).

The claim being tested is that a reader can reproduce the published numbers with
no credentials, no local model and no GPU.

**What is byte-identical, and what cannot be.** Every model-derived value is:
the raw responses, the patches built from them, the band-aid classifications,
the sleep durations, and the token counts. Those are the numbers the comparison
rests on and they replay exactly.

Execution-derived values cannot be byte-identical and it would be dishonest to
claim otherwise. The benchmark races are genuinely nondeterministic — that is
what makes them a benchmark — so observed flake rates, wall-clock timings and
the statistical tier's pass counts differ between runs by design. This module
therefore compares the model-derived fields exactly and reports the
execution-derived ones as reproducible-in-distribution rather than in value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ReplayComparison", "compare"]

EXACT_FIELDS = (
    "arm",
    "case_id",
    "band_aid",
    "band_aid_rules",
    "band_aid_detail",
    "modified_file",
    "sleep_seconds_added",
    "tokens_input",
    "tokens_output",
    "model_calls",
    "attempts_used",
)
"""Model-derived fields that must replay byte-for-byte."""

NONDETERMINISTIC_FIELDS = (
    "wall_clock_s",
    "ui_state",
    "verified_repair",
    "tier_reached",
)
"""Execution-derived fields. Compared and reported, never asserted."""


@dataclass
class ReplayComparison:
    """The outcome of comparing a live run against its replay."""

    exact_matches: int = 0
    exact_mismatches: list[str] = field(default_factory=list)
    drifted: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def model_derived_identical(self) -> bool:
        """True when every model-derived field replayed byte-for-byte."""
        return not self.exact_mismatches and not self.missing

    def render(self) -> str:
        """Human-readable verdict."""
        lines = [
            f"Model-derived fields identical: {self.model_derived_identical} "
            f"({self.exact_matches} field comparisons across all arm/case pairs)"
        ]
        if self.missing:
            lines.append(f"Missing from replay: {', '.join(self.missing)}")
        for mismatch in self.exact_mismatches:
            lines.append(f"MISMATCH {mismatch}")
        if self.drifted:
            lines.append(
                "Execution-derived fields that differ between runs (expected — the "
                "benchmark races are nondeterministic by construction):"
            )
            lines.extend(f"  {item}" for item in self.drifted)
        return "\n".join(lines)


def compare(live_path: Path, replay_path: Path) -> ReplayComparison:
    """Compare a live sweep's results against a fixture replay of the same sweep.

    Args:
        live_path: Results JSON from the model-backed run.
        replay_path: Results JSON from the fixture-backed run.

    Returns:
        The comparison.

    """
    live = json.loads(live_path.read_text())
    replay = json.loads(replay_path.read_text())
    live_index = {(r["arm"], r["case_id"]): r for r in live["results"]}
    replay_index = {(r["arm"], r["case_id"]): r for r in replay["results"]}

    comparison = ReplayComparison()
    for key, original in sorted(live_index.items()):
        replayed = replay_index.get(key)
        if replayed is None:
            comparison.missing.append(f"{key[0]}/{key[1]}")
            continue
        for field_name in EXACT_FIELDS:
            comparison.exact_matches += 1
            if original.get(field_name) != replayed.get(field_name):
                comparison.exact_mismatches.append(
                    f"{key[0]}/{key[1]}.{field_name}: "
                    f"{original.get(field_name)!r} != {replayed.get(field_name)!r}"
                )
        for field_name in NONDETERMINISTIC_FIELDS:
            if original.get(field_name) != replayed.get(field_name):
                comparison.drifted.append(
                    f"{key[0]}/{key[1]}.{field_name}: "
                    f"{original.get(field_name)!r} -> {replayed.get(field_name)!r}"
                )
    return comparison
