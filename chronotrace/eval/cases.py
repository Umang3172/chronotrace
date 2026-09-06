"""Benchmark case loading (spec 25).

The corpus is **seeded, not mined from the wild**, and labelled as such
everywhere it is reported. No public Python concurrency flaky-test dataset
exists; iDoFT is Java and order-dependent-biased, and ReproFlake is Java too.
Saying so costs nothing and hiding it would cost everything.

Ground truth is recorded per case so that correctness is checkable rather than
inferred from greenness — a test that passes for the wrong reason is a failure,
not a repair.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = ["BenchmarkCase", "load_cases"]


@dataclass(frozen=True)
class BenchmarkCase:
    """One seeded case and its expected outcome."""

    case_id: str
    name: str
    test_id: str
    expected_ui_state: str
    expected_transformation: str | None
    expected_abstain_reason: str | None
    is_control: bool
    band_aid_would_pass: bool
    shape: str
    notes: str
    directory: Path

    @property
    def is_supported_race(self) -> bool:
        """True for cases ChronoTrace is expected to repair."""
        return self.expected_ui_state == "FIXED"


def load_cases(root: Path) -> list[BenchmarkCase]:
    """Load every benchmark case under ``root``, ordered by case id.

    Args:
        root: The ``benchmark/cases`` directory.

    Returns:
        Every case with a ``ground_truth.json``.

    """
    cases: list[BenchmarkCase] = []
    for path in sorted(root.glob("*/ground_truth.json")):
        data = json.loads(path.read_text())
        cases.append(
            BenchmarkCase(
                case_id=data["id"],
                name=data["name"],
                test_id=data["test_id"],
                expected_ui_state=data["expected_ui_state"],
                expected_transformation=data.get("expected_transformation"),
                expected_abstain_reason=data.get("expected_abstain_reason"),
                is_control=bool(data.get("control", False)),
                band_aid_would_pass=bool(data.get("band_aid_would_pass", False)),
                shape=data.get("shape", data.get("true_cause", "")),
                notes=data.get("notes", ""),
                directory=path.parent,
            )
        )
    return cases
