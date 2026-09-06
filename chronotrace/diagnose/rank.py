"""Candidate inversion detection and ranking (spec 9.1 stage 2, D-4..D-7).

An inverted pair is two operations observed in one order when the test passes
and the other order when it fails. Finding them is cheap; deciding which one
matters is the problem.

**Absence is evidence.** In a failing run the write that should have happened
often never happens at all — the assertion fails and the test unwinds before the
writer resumes. In a run that flushed its spans normally, an operation observed
elsewhere but missing here did not start within the observed window, so it is
ordered last. In a run that crashed or hung (``complete=False``) the same
absence means nothing and the pair is skipped (D4).

Ranking uses Ochiai suspiciousness, borrowed from spectrum-based fault
localization, over *all* captured traces rather than one pass and one fail: an
ordering seen in every failure and no pass is a strong candidate, one seen in
half of each is noise. Ties break by causal position, earliest first, because a
later divergence is usually determined by an earlier one (D-7) — ranking by
proximity to the assertion biases toward the symptom.

Iteration order is sorted everywhere. Nondeterministic output from a
determinism tool would be indefensible (D-5).
"""

from __future__ import annotations

import math
from collections import defaultdict

from chronotrace.contracts import CandidateInversion, SpanRecord, TraceCapture
from chronotrace.diagnose.graph import ObservedOrderGraph, build, to_operation_ref

__all__ = ["candidates"]


def _pairs_sharing_state(graphs: list[ObservedOrderGraph]) -> set[tuple[str, str]]:
    """Return unordered pairs that touch the same resource, at least one writing.

    Two operations that never touch shared state cannot race, so pairs are
    restricted to those that do. This is a soundness-preserving filter on the
    candidate set, not a heuristic ranking.

    Assertion spans are excluded. The assertion is the observation point and the
    root of the backward slice, not an operation that can be reordered against
    another; treating it as a candidate is precisely the bias toward the symptom
    that D-7 warns about.
    """
    by_resource: dict[str, set[str]] = {}
    access: dict[str, str | None] = {}
    for graph in graphs:
        for resource, keys in graph.resources.items():
            operations = {
                key for key in keys if not graph.spans[key].attributes.get("ct.assertion")
            }
            by_resource.setdefault(resource, set()).update(operations)
        for key in graph.spans:
            access.setdefault(key, graph.access_of(key))
    found: set[tuple[str, str]] = set()
    for keys in by_resource.values():
        ordered = sorted(keys)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if "write" in (access.get(left), access.get(right)):
                    found.add((left, right))
    return found


def candidates(
    passing: list[TraceCapture],
    failing: list[TraceCapture],
    sliced: set[str],
) -> list[CandidateInversion]:
    """Rank every inverted pair observed between passing and failing runs.

    Args:
        passing: Passing captures.
        failing: Failing captures.
        sliced: Operation keys in the backward slice of the failed assertion.

    Returns:
        Candidates ordered best-first: in-slice before out-of-slice, then by
        descending Ochiai score, then by earliest causal position.

    """
    pass_graphs = [build(capture) for capture in passing]
    fail_graphs = [build(capture) for capture in failing]
    if not pass_graphs or not fail_graphs:
        return []

    graphs = fail_graphs + pass_graphs
    shared = _pairs_sharing_state(graphs)
    spans = _span_index(graphs)

    fail_counts: dict[tuple[str, str], int] = defaultdict(int)
    pass_counts: dict[tuple[str, str], int] = defaultdict(int)
    for graph in fail_graphs:
        for pair in sorted(shared):
            ordered = _observed(graph, pair)
            if ordered is not None:
                fail_counts[ordered] += 1
    for graph in pass_graphs:
        for pair in sorted(shared):
            ordered = _observed(graph, pair)
            if ordered is not None:
                pass_counts[ordered] += 1

    total_failing = len(fail_graphs)
    results: list[CandidateInversion] = []
    for pair in sorted(shared):
        left, right = pair
        forward, backward = (left, right), (right, left)
        if fail_counts[forward] and pass_counts[backward]:
            failing_order = forward
        elif fail_counts[backward] and pass_counts[forward]:
            failing_order = backward
        else:
            continue
        results.append(
            CandidateInversion(
                op_a=to_operation_ref(spans[failing_order[0]]),
                op_b=to_operation_ref(spans[failing_order[1]]),
                causal_position=_causal_position(fail_graphs, failing_order),
                ochiai_score=round(
                    _ochiai(fail_counts[failing_order], pass_counts[failing_order], total_failing),
                    4,
                ),
                in_backward_slice=failing_order[0] in sliced and failing_order[1] in sliced,
                classification="UNTESTED",
                failing_order=list(failing_order),
            )
        )

    results.sort(
        key=lambda item: (
            not item.in_backward_slice,
            -item.ochiai_score,
            item.causal_position,
            item.op_a.key,
            item.op_b.key,
        )
    )
    return results


def _span_index(graphs: list[ObservedOrderGraph]) -> dict[str, SpanRecord]:
    spans: dict[str, SpanRecord] = {}
    for graph in graphs:
        for key, span in graph.spans.items():
            spans.setdefault(key, span)
    return spans


def _observed(graph: ObservedOrderGraph, pair: tuple[str, str]) -> tuple[str, str] | None:
    left, right = pair
    left_seen, right_seen = left in graph.position, right in graph.position
    if left_seen and right_seen:
        return (left, right) if graph.precedes(left, right) else (right, left)
    if not graph.complete:
        return None
    if left_seen:
        return (left, right)
    if right_seen:
        return (right, left)
    return None


def _causal_position(fail_graphs: list[ObservedOrderGraph], order: tuple[str, str]) -> int:
    """Position of the earliest involved operation in the failing runs (D-7).

    Measured in the execution being explained, so that candidates are ranked by
    how early they diverge rather than by how close they sit to the assertion.
    """
    positions = [
        graph.position[key] for graph in fail_graphs for key in order if key in graph.position
    ]
    return min(positions) if positions else len(fail_graphs[0].order)


def _ochiai(failed_with: int, passed_with: int, total_failing: int) -> float:
    """Ochiai suspiciousness of an ordering.

    ``failed / sqrt(total_failing * (failed + passed))`` — 1.0 when an ordering
    appears in every failing run and no passing run.
    """
    denominator = math.sqrt(total_failing * (failed_with + passed_with))
    if denominator == 0:
        return 0.0
    return failed_with / denominator
