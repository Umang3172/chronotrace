"""Positive rules: what a patch must contain (spec 24, P1-P3; G-1).

A negative-only governor is satisfiable by doing nothing: an empty patch injects
no sleeps and passes every ban, which would make "0% band-aid rate" a metric a
no-op can achieve. These three rules close that hole.
"""

from __future__ import annotations

import ast

from chronotrace.govern.negative import Finding
from chronotrace.govern.resolve import build_table

__all__ = ["check_positive"]

PRIMITIVES = {
    "asyncio.Event",
    "asyncio.Barrier",
    "asyncio.Condition",
    "asyncio.Lock",
    "asyncio.Semaphore",
}


def check_positive(before: str, after: str) -> list[Finding]:
    """Return violations of the positive rules.

    Args:
        before: Source before the patch.
        after: Source after the patch.

    Returns:
        Findings for each positive requirement the patch fails to meet.

    """
    pre, post = ast.parse(before), ast.parse(after)
    findings: list[Finding] = []

    if _normalise(pre) == _normalise(post):
        findings.append(Finding("P3", "patch is a no-op: the module's syntax tree is unchanged"))
        return findings

    added_primitives = _primitive_names(post) - _primitive_names(pre)
    added_awaits = _awaited_names(post) - _awaited_names(pre)
    if not added_primitives and not added_awaits:
        findings.append(
            Finding(
                "P1",
                "patch adds no synchronization primitive and no new await; something "
                "changed, but nothing that establishes an ordering",
            )
        )
        return findings

    for name in sorted(added_primitives):
        signallers = _functions_referencing(post, name, kind="set")
        waiters = _functions_referencing(post, name, kind="wait")
        if not signallers or not waiters:
            findings.append(
                Finding(
                    "P2",
                    f"primitive {name!r} is signalled in {sorted(signallers) or 'no function'} "
                    f"and awaited in {sorted(waiters) or 'no function'}; a race is between "
                    "two coroutines, so both sides are required",
                )
            )
        elif signallers == waiters:
            findings.append(
                Finding(
                    "P2",
                    f"primitive {name!r} is signalled and awaited only in "
                    f"{sorted(signallers)}; within one coroutine the operations are "
                    "already ordered and the primitive is a no-op",
                )
            )
    return findings


def _normalise(tree: ast.AST) -> str:
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def _primitive_names(tree: ast.AST) -> set[str]:
    """Return names bound to a newly constructed asyncio primitive."""
    table = build_table(tree)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if not table.resolves_to(node.value.func, PRIMITIVES):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _awaited_names(tree: ast.AST) -> set[str]:
    """Return names that are awaited directly, e.g. an added ``await task``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Name):
            names.add(node.value.id)
    return names


def _functions_referencing(tree: ast.AST, name: str, *, kind: str) -> set[str]:
    """Return functions calling ``name.set()`` or awaiting ``name.wait()``."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute):
                continue
            target = inner.func
            if not isinstance(target.value, ast.Name) or target.value.id != name:
                continue
            if kind == "set" and target.attr in {"set", "release"}:
                found.add(node.name)
            if kind == "wait" and target.attr in {"wait", "acquire"}:
                found.add(node.name)
    return found
