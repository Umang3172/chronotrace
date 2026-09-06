"""Backward slice from the failed assertion (spec 9.1, stage 1).

With four concurrent tasks a run yields dozens of inverted pairs, and almost
none of them matter — tasks legitimately interleave differently every time.
Returning the first inversion found is the wrong algorithm.

Classic program slicing prunes the candidate set for free: start at the value
the failed assertion read, walk backwards through the operations that could
have produced it, and keep only inversions that touch that slice.

The walk spans every captured trace, not just the failing one. An operation
that is *missing* from a failing run — the write that never happened — is
exactly the operation the slice needs to include.
"""

from __future__ import annotations

from chronotrace.diagnose.graph import ObservedOrderGraph

__all__ = ["backward_slice"]


def backward_slice(
    graphs: list[ObservedOrderGraph], failing_resource: str | None
) -> tuple[set[str], set[str]]:
    """Return the operations and resources the failed assertion could have depended on.

    Args:
        graphs: Every captured run's graph, failing runs first.
        failing_resource: Resource read by the failed assertion. When unknown,
            the slice falls back to every operation touching shared state, which
            prunes nothing but never hides the real candidate.

    Returns:
        ``(operation_keys, resource_names)`` in the slice.

    """
    resource_index: dict[str, set[str]] = {}
    ancestors: dict[str, set[str]] = {}
    resource_of: dict[str, str] = {}
    for graph in graphs:
        for resource, keys in graph.resources.items():
            resource_index.setdefault(resource, set()).update(keys)
            for key in keys:
                resource_of[key] = resource
        for key in graph.spans:
            ancestors.setdefault(key, set()).update(_ancestors(graph, key))

    if failing_resource is None:
        return set(resource_of), set(resource_index)

    frontier = {failing_resource}
    seen_resources: set[str] = set()
    sliced: set[str] = set()
    while frontier:
        resource = frontier.pop()
        if resource in seen_resources:
            continue
        seen_resources.add(resource)
        touching = resource_index.get(resource, set())
        sliced |= touching
        for key in touching:
            for ancestor in ancestors.get(key, set()):
                ancestor_resource = resource_of.get(ancestor)
                if ancestor_resource and ancestor_resource not in seen_resources:
                    frontier.add(ancestor_resource)
    return sliced, seen_resources


def _ancestors(graph: ObservedOrderGraph, key: str) -> set[str]:
    return {other for other, reachable in graph.descendants.items() if key in reachable}
