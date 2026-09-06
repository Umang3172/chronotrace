"""Diagnosis orchestration: from captured traces to a decided :class:`Diagnosis`.

The order of the checks is the design. Paradigm and trace-pair availability are
settled before any graph is built, because a race in threads and a test with no
passing run are refusals, not diagnoses. Only after an inversion survives
slicing, ranking *and* forced replay is a race called proven — and a proven race
in production code is still a refusal (D8 / INV-7).
"""

from __future__ import annotations

from pathlib import Path

from chronotrace.contracts import CandidateInversion, CaptureBundle, Diagnosis
from chronotrace.diagnose import abstain, rank
from chronotrace.diagnose import slice as slice_mod
from chronotrace.diagnose.depth import ConfirmationBudget, confirm
from chronotrace.diagnose.graph import build, is_third_party
from chronotrace.logging import get_logger

log = get_logger(__name__)

__all__ = ["diagnose"]

MIN_SLICE_OPERATIONS = 2


def diagnose(
    bundle: CaptureBundle,
    *,
    cwd: Path,
    budget: ConfirmationBudget | None = None,
    timeout_s: float = 30.0,
    gate_timeout_s: float = 5.0,
    allow_production_repair: bool = False,
) -> Diagnosis:
    """Decide what, if anything, ChronoTrace can prove about a flaky test.

    Args:
        bundle: Captured traces for the test.
        cwd: Repository root, used for forced confirmation runs.
        budget: How many candidates and runs confirmation may spend.
        timeout_s: Per-run wall-clock cap.
        gate_timeout_s: Cap on one forced-ordering gate.
        allow_production_repair: Opt in to diagnosing races in product code
            (INV-7). Off by default.

    Returns:
        A diagnosis whose status is RACE_PROVEN, NEEDS_INVESTIGATION or
        ABSTAINED, always with a plain-language explanation.

    """
    test_path = abstain.test_file_of(bundle.test_id)
    paradigm = abstain.detect_paradigm(cwd / test_path)
    if paradigm in {"threading", "multiprocessing"}:
        return _abstained(
            "NON_ASYNCIO_PARADIGM",
            f"This test uses {paradigm}. ChronoTrace can only control the asyncio "
            "event loop, so it cannot prove an ordering here and will not guess.",
        )

    if not bundle.has_pair:
        observed = "only passing runs" if bundle.passing else "only failing runs"
        return _abstained(
            "NO_TRACE_PAIR",
            f"The capture budget produced {observed} ({bundle.runs_executed} runs). "
            "Diagnosis compares a passing execution against a failing one; there is "
            "nothing to compare.",
        )

    failing = bundle.failing[0]
    failing_graph = build(failing)
    all_graphs = [build(capture) for capture in bundle.failing + bundle.passing]
    third_party = [
        key
        for key in sorted(failing_graph.spans)
        if is_third_party(failing_graph.spans[key].source_file)
    ]
    if third_party and len(third_party) == len(failing_graph.spans):
        return _abstained(
            "THIRD_PARTY_CODE",
            "Every operation in the failing trace comes from installed dependency "
            "code. ChronoTrace does not patch third-party packages.",
        )

    sliced, _resources = slice_mod.backward_slice(all_graphs, failing.failing_resource)
    slice_names = {
        graph.spans[key].name for graph in all_graphs for key in sliced if key in graph.spans
    }
    if len(slice_names) < MIN_SLICE_OPERATIONS:
        return _abstained(
            "SPAN_GRANULARITY_TOO_COARSE",
            "The failed assertion depends on fewer than two observable operations, "
            "so any race inside them is invisible at this granularity. Localising "
            "here would point at the wrong place.",
        )

    found = rank.candidates(bundle.passing, bundle.failing, sliced)
    if not found:
        sources = abstain.nondeterministic_sources(cwd / test_path)
        if not abstain.assertion_failed(failing):
            return _abstained(
                "NOT_A_RACE",
                "The failing run did not reach its assertion — it raised before "
                "getting there. That is not evidence about a schedule.",
                candidates_evaluated=0,
            )
        if sources:
            return _abstained(
                "NOT_A_RACE",
                "Passing and failing runs executed operations in the same order, and "
                "this test draws on " + ", ".join(sources) + ". The nondeterminism is "
                "in the data, not the schedule.",
                candidates_evaluated=0,
            )
        return _abstained(
            "NO_INVERSION",
            "Passing and failing runs executed the same operations in the same order. "
            "Whatever varies between them is not visible as an ordering difference.",
            candidates_evaluated=0,
        )

    classified, deadlock = confirm(
        found,
        test_id=bundle.test_id,
        cwd=cwd,
        budget=budget,
        timeout_s=timeout_s,
        gate_timeout_s=gate_timeout_s,
    )
    proven = next(
        (item for item in classified if item.classification == "CAUSALLY_SUFFICIENT"), None
    )
    if proven is not None:
        production_scope = not (proven.op_a.is_test_scope and proven.op_b.is_test_scope)
        if production_scope and not allow_production_repair:
            return _abstained(
                "PRODUCTION_SCOPE_RACE",
                "The proven race is between operations in application code "
                f"({proven.op_a.source_file}), not test code. Repairing the test "
                "would hide a real product defect. Re-run with "
                "--allow-production-repair to proceed deliberately.",
                candidates_evaluated=len(classified),
                candidates=classified,
                proven_inversion=proven,
            )
        return Diagnosis(
            status="RACE_PROVEN",
            proven_inversion=proven,
            bug_depth=1,
            candidates_evaluated=len(classified),
            candidates=classified,
            explanation=(
                f"Forcing {proven.op_a.span_name} to start before {proven.op_b.span_name} "
                "reproduced the failure on every attempt, so that ordering is a "
                "sufficient condition for the failure."
            ),
        )

    insufficient = [item for item in classified if item.classification == "NECESSARY_INSUFFICIENT"]
    if insufficient:
        best = insufficient[0]
        rate = best.forced_failure_rate or 0.0
        return Diagnosis(
            status="NEEDS_INVESTIGATION",
            abstain_reason="DEPTH_GE_2_UNRESOLVED",
            candidates_evaluated=len(classified),
            candidates=classified,
            proven_inversion=None,
            explanation=(
                f"Forcing {best.op_a.span_name} before {best.op_b.span_name} failed "
                f"{rate:.0%} of the time — necessary but not sufficient. This race needs "
                "at least two scheduling constraints; the minimal sufficient set was not "
                "found within budget, so no patch was generated."
            ),
        )

    if deadlock:
        return _abstained(
            "NOT_A_RACE",
            "Forced replay timed out rather than failing, which is a hang signal "
            "rather than a race we can prove.",
            candidates_evaluated=len(classified),
            candidates=classified,
        )

    return Diagnosis(
        status="NEEDS_INVESTIGATION",
        abstain_reason=None,
        candidates_evaluated=len(classified),
        candidates=classified,
        explanation=(
            "Ordering differences were found between passing and failing runs, but "
            "forcing them did not reproduce the failure. They are correlated with the "
            "failure, not causing it."
        ),
    )


def _abstained(
    reason: str,
    explanation: str,
    *,
    candidates_evaluated: int = 0,
    candidates: list[CandidateInversion] | None = None,
    proven_inversion: CandidateInversion | None = None,
) -> Diagnosis:
    log.info("diagnose.abstain", reason=reason)
    return Diagnosis(
        status="ABSTAINED",
        abstain_reason=reason,  # type: ignore[arg-type]
        candidates_evaluated=candidates_evaluated,
        candidates=candidates or [],
        proven_inversion=proven_inversion,
        explanation=explanation,
    )
