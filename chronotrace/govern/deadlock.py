"""Deadlock pre-check: wait-for graph cycle detection (INV-3, G-5, S1).

The repair mechanism injects waits, which is precisely the mechanism that
creates deadlocks. If A waits for B while B already waits for A, an
intermittent failure becomes a permanent hang — a flake costs an hour, a
deadlocked CI suite costs a day.

The check is static, cheap and runs *before* the patch is ever executed: add the
proposed wait edge to the wait-for graph and reject on a cycle.
"""

from __future__ import annotations

import ast

import networkx as nx

__all__ = ["find_cycle", "wait_for_graph"]


def wait_for_graph(source: str) -> nx.DiGraph[str]:
    """Build the wait-for graph of a module.

    An edge ``waiter -> signaller`` means the waiting function cannot proceed
    until the signalling function runs.

    Args:
        source: Module source, normally the post-patch version.

    Returns:
        The directed wait-for graph over function names.

    """
    tree = ast.parse(source)
    waits: dict[str, set[str]] = {}
    signals: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute):
                continue
            attribute = inner.func
            if not isinstance(attribute.value, ast.Name):
                continue
            primitive = attribute.value.id
            if attribute.attr in {"wait", "acquire"}:
                waits.setdefault(primitive, set()).add(node.name)
            elif attribute.attr in {"set", "release"}:
                signals.setdefault(primitive, set()).add(node.name)

    graph: nx.DiGraph[str] = nx.DiGraph()
    for primitive, waiters in waits.items():
        for waiter in waiters:
            graph.add_node(waiter)
            for signaller in signals.get(primitive, set()):
                graph.add_node(signaller)
                if waiter != signaller:
                    graph.add_edge(waiter, signaller, primitive=primitive)
    return graph


def find_cycle(source: str) -> list[str] | None:
    """Return a wait-for cycle in ``source``, or None when the graph is acyclic.

    Args:
        source: Module source to check.

    Returns:
        The function names forming a cycle, or None.

    """
    graph = wait_for_graph(source)
    try:
        cycle = nx.find_cycle(graph, orientation="original")
    except nx.NetworkXNoCycle:
        return None
    return [str(edge[0]) for edge in cycle]
