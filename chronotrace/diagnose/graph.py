"""Observed-order graph construction (D-1, D-2).

**Naming honesty (INV-10).** The order here is derived from observed start
times plus structural edges, not from a partial order over synchronization
events. It is therefore *observed order*, never "happens-before". Claiming
Lamport while shipping a timestamp sort is exactly the thing a reviewer catches.

The draft spec built edges from resource access alone, which left the graph
mostly disconnected and made reachability queries useless (D-2). Three edge
sources are built here:

* **parent-child** — a span nested inside another,
* **program order** — consecutive spans within the same asyncio task,
* **resource access** — spans touching the same shared resource.

Reachability is computed once into per-node descendant sets rather than per pair
(D-4), and every node is keyed by name *and occurrence* (D-3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

import networkx as nx

from chronotrace.contracts import OperationRef, SpanRecord, TraceCapture

__all__ = ["ObservedOrderGraph", "build"]


def _sort_key(span: SpanRecord) -> tuple[int, str, int]:
    return (span.start_ns, span.name, span.occurrence)


def is_test_scope(source_file: str | None) -> bool:
    """Return True when ``source_file`` belongs to test code rather than product code."""
    if not source_file:
        return True
    name = source_file.replace("\\", "/")
    base = name.rsplit("/", 1)[-1]
    return base.startswith("test_") or base == "conftest.py" or "/tests/" in name


def is_third_party(source_file: str | None) -> bool:
    """Return True when ``source_file`` is vendored or installed dependency code (INV-6)."""
    if not source_file:
        return False
    name = source_file.replace("\\", "/")
    return "/site-packages/" in name or "/dist-packages/" in name or "/vendor/" in name


def to_operation_ref(span: SpanRecord) -> OperationRef:
    """Build a stable operation identity from a span (never substring matching — P-2)."""
    qualname = str(span.attributes.get("ct.qualname", span.name))
    access = str(span.attributes.get("ct.access", "unknown"))
    resource = span.attributes.get("ct.resource")
    return OperationRef(
        span_name=span.name,
        occurrence=span.occurrence,
        source_file=span.source_file or "<unknown>",
        source_line=span.source_line or 0,
        qualname=qualname,
        is_test_scope=is_test_scope(span.source_file),
        access=access if access in {"read", "write"} else "unknown",  # type: ignore[arg-type]
        resource=str(resource) if resource is not None else None,
    )


@dataclass
class ObservedOrderGraph:
    """A single execution rendered as a directed acyclic graph of operations."""

    graph: nx.DiGraph[str]
    spans: dict[str, SpanRecord]
    order: list[str]
    """Operation keys in observed start order."""
    complete: bool = True
    """False when the run crashed or hung before spans were flushed (D4)."""
    position: dict[str, int] = field(default_factory=dict)
    descendants: dict[str, set[str]] = field(default_factory=dict)
    resources: dict[str, set[str]] = field(default_factory=dict)
    """Resource name -> operation keys touching it."""

    def precedes(self, left: str, right: str) -> bool:
        """Return True when ``left`` was observed to start before ``right``."""
        return self.position[left] < self.position[right]

    def reaches(self, left: str, right: str) -> bool:
        """Return True when ``right`` is reachable from ``left`` in the graph."""
        return right in self.descendants.get(left, set())

    def resource_of(self, key: str) -> str | None:
        """Return the shared resource an operation touches, if it declared one."""
        span = self.spans[key]
        value = span.attributes.get("ct.resource")
        return str(value) if value is not None else None

    def access_of(self, key: str) -> str | None:
        """Return ``"read"`` or ``"write"`` for an operation, if declared."""
        span = self.spans[key]
        value = span.attributes.get("ct.access")
        return str(value) if value is not None else None


def build(capture: TraceCapture) -> ObservedOrderGraph:
    """Build the observed-order graph for one execution.

    Args:
        capture: A single captured run.

    Returns:
        The graph, with reachability and resource indexes precomputed.

    """
    spans = sorted(capture.spans, key=_sort_key)
    by_key = {span.key: span for span in spans}
    order = [span.key for span in spans]
    position = {key: index for index, key in enumerate(order)}

    graph: nx.DiGraph[str] = nx.DiGraph()
    for span in spans:
        graph.add_node(span.key, name=span.name, occurrence=span.occurrence)

    def add_edge(earlier: str, later: str, kind: str) -> None:
        """Record an ordering edge, accumulating every reason for it.

        One pair can be ordered for several reasons at once — nested *and*
        sequential in the same task *and* touching the same resource. Keeping
        all of them means the graph can explain itself rather than reporting
        whichever reason was added last.
        """
        kinds: list[str] = (
            graph.edges[earlier, later]["kinds"] if graph.has_edge(earlier, later) else []
        )
        if kind not in kinds:
            kinds = [*kinds, kind]
        graph.add_edge(earlier, later, kinds=kinds, kind=kinds[0])

    by_span_id = {span.span_id: span for span in spans}
    for span in spans:
        if span.parent_span_id and span.parent_span_id in by_span_id:
            parent = by_span_id[span.parent_span_id]
            if position[parent.key] < position[span.key]:
                add_edge(parent.key, span.key, "parent_child")

    by_task: dict[str, list[SpanRecord]] = {}
    for span in spans:
        by_task.setdefault(span.task_name or "<unknown>", []).append(span)
    for task_spans in by_task.values():
        for earlier, later in pairwise(task_spans):
            add_edge(earlier.key, later.key, "program_order")

    resources: dict[str, set[str]] = {}
    by_resource: dict[str, list[SpanRecord]] = {}
    for span in spans:
        resource = span.attributes.get("ct.resource")
        if resource is None:
            continue
        by_resource.setdefault(str(resource), []).append(span)
        resources.setdefault(str(resource), set()).add(span.key)
    for resource_spans in by_resource.values():
        for earlier, later in pairwise(resource_spans):
            add_edge(earlier.key, later.key, "resource_access")

    descendants = {key: set(nx.descendants(graph, key)) for key in graph.nodes}
    return ObservedOrderGraph(
        graph=graph,
        complete=capture.complete,
        spans=by_key,
        order=order,
        position=position,
        descendants=descendants,
        resources=resources,
    )
