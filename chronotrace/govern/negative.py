"""Negative rules: constructs a patch may not introduce (spec 24, N1-N8).

This is the anti-band-aid gate and the project's central differentiator. Every
rule here is a safety check, so the set is implemented in full: a governor that
catches ``time.sleep`` but not ``from time import sleep as s`` is not a weaker
governor, it is a bypass.

Rules compare **counts before and after** rather than scanning the patched file
alone. A test that already contained a sleep must still be repairable; what is
forbidden is the patch *adding* one.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from chronotrace.govern.resolve import build_table

__all__ = ["Finding", "check_negative"]

SLEEP_TARGETS = {"time.sleep", "asyncio.sleep", "anyio.sleep", "trio.sleep"}
RETRY_DECORATORS = {
    "flaky.flaky",
    "pytest.mark.flaky",
    "tenacity.retry",
    "retry.retry",
    "retrying.retry",
    "backoff.on_exception",
}
SKIP_DECORATORS = {"pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail"}
TIMEOUT_DECORATORS = {"pytest.mark.timeout", "timeout_decorator.timeout"}
WEAKENING_METHODS = {"assertIn", "assertAlmostEqual", "assertTrue", "assertIsNotNone"}


@dataclass(frozen=True)
class Finding:
    """One policy violation."""

    rule_id: str
    detail: str


def check_negative(before: str, after: str) -> list[Finding]:
    """Return every negative-rule violation the patch introduces.

    Args:
        before: Source before the patch.
        after: Source after the patch.

    Returns:
        Findings, one per violated rule, in rule order.

    """
    pre, post = ast.parse(before), ast.parse(after)
    findings: list[Finding] = []
    findings += _n1_n2_sleeps(pre, post)
    findings += _n3_timeouts(pre, post)
    findings += _n4_retry_decorators(pre, post)
    findings += _n5_retry_loops(pre, post)
    findings += _n6_weakened_assertions(pre, post)
    findings += _n7_swallowed_failures(pre, post)
    findings += _n8_decollected_tests(pre, post)
    return findings


def _sleep_calls(tree: ast.AST) -> tuple[list[str], list[str]]:
    """Return sleep calls split into (written as a sleep, reached through an alias).

    The split is what separates N1 from N2. A call is aliased when the name in
    the source does not match the symbol it resolves to, which is exactly the
    ``from time import sleep as s`` evasion.
    """
    table = build_table(tree)
    direct: list[str] = []
    aliased: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not table.resolves_to(node.func, SLEEP_TARGETS):
            continue
        resolved = table.resolve(node.func) or "sleep"
        written = ast.unparse(node.func)
        (aliased if written != resolved else direct).append(f"{written} -> {resolved}")
    return sorted(direct), sorted(aliased)


def _n1_n2_sleeps(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N1/N2: sleeps, including aliased imports, resolved through the import table."""
    pre_direct, pre_aliased = _sleep_calls(pre)
    post_direct, post_aliased = _sleep_calls(post)
    findings: list[Finding] = []
    if len(post_direct) > len(pre_direct):
        names = sorted(set(post_direct) - set(pre_direct)) or ["sleep"]
        findings.append(
            Finding(
                "N1",
                f"patch adds {len(post_direct) - len(pre_direct)} sleep call(s) "
                f"({', '.join(names)}); a timing delay hides the race and adds permanent "
                "CI cost",
            )
        )
    if len(post_aliased) > len(pre_aliased):
        names = sorted(set(post_aliased) - set(pre_aliased)) or ["sleep"]
        findings.append(
            Finding(
                "N2",
                f"patch adds {len(post_aliased) - len(pre_aliased)} sleep call(s) reached "
                f"through an import alias ({', '.join(names)}); the alias is resolved, not "
                "matched on name text",
            )
        )
    return findings


def _decorator_targets(tree: ast.AST, targets: set[str]) -> dict[str, list[ast.expr]]:
    table = build_table(tree)
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            base = decorator.func if isinstance(decorator, ast.Call) else decorator
            if table.resolves_to(base, targets):
                found.setdefault(node.name, []).append(decorator)
    return found


def _n3_timeouts(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N3: a timeout marker added, or an existing one increased (needs the diff — G-3)."""
    before = _timeout_values(pre)
    after = _timeout_values(post)
    findings = []
    for name, value in sorted(after.items()):
        if name not in before:
            findings.append(
                Finding("N3", f"patch adds a timeout marker to {name!r} (value {value})")
            )
        elif value is not None and (previous := before[name]) is not None and value > previous:
            findings.append(
                Finding(
                    "N3",
                    f"patch inflates the timeout on {name!r} from {before[name]} to {value}",
                )
            )
    return findings


def _timeout_values(tree: ast.AST) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for name, decorators in _decorator_targets(tree, TIMEOUT_DECORATORS).items():
        for decorator in decorators:
            value: float | None = None
            if isinstance(decorator, ast.Call) and decorator.args:
                argument = decorator.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, int | float):
                    value = float(argument.value)
            values[name] = value
    return values


def _n4_retry_decorators(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N4: retry and flaky decorators, resolved rather than name-matched (G-4)."""
    before = set(_decorator_targets(pre, RETRY_DECORATORS))
    after = set(_decorator_targets(post, RETRY_DECORATORS))
    added = sorted(after - before)
    if not added:
        return []
    return [
        Finding(
            "N4",
            f"patch adds a retry/flaky decorator to {', '.join(repr(n) for n in added)}; "
            "retrying a race hides it",
        )
    ]


def _retry_loops(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.While | ast.For):
            continue
        wraps_assert = any(isinstance(inner, ast.Assert) for inner in ast.walk(node))
        breaks_out = isinstance(node, ast.While) and any(
            isinstance(inner, ast.Break) for inner in ast.walk(node)
        )
        if wraps_assert or breaks_out:
            count += 1
    return count


def _n5_retry_loops(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N5: a loop wrapped around the assertion, bounded or not."""
    added = _retry_loops(post) - _retry_loops(pre)
    if added <= 0:
        return []
    return [
        Finding(
            "N5",
            f"patch adds {added} retry loop(s) around an assertion; polling until the "
            "state arrives is a sleep with extra steps",
        )
    ]


def _assert_profile(tree: ast.AST) -> tuple[int, list[str], int]:
    asserts = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    operators = sorted(
        type(op).__name__
        for node in asserts
        if isinstance(node.test, ast.Compare)
        for op in node.test.ops
    )
    weakening = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in WEAKENING_METHODS
    )
    return len(asserts), operators, weakening


def _n6_weakened_assertions(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N6: assertions removed or loosened. Requires the pre/post comparison."""
    before_count, before_ops, before_weak = _assert_profile(pre)
    after_count, after_ops, after_weak = _assert_profile(post)
    findings = []
    if after_count < before_count:
        findings.append(Finding("N6", f"patch removes {before_count - after_count} assertion(s)"))
    tightening = {"Eq", "Is", "NotIn"}
    lost = [op for op in before_ops if op in tightening and op not in after_ops]
    if lost:
        findings.append(
            Finding("N6", f"patch replaces strict comparison(s) {', '.join(sorted(set(lost)))}")
        )
    if after_weak > before_weak:
        findings.append(Finding("N6", "patch introduces a looser unittest assertion method"))
    return findings


def _handlers_around_asserts(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            isinstance(inner, ast.Assert) for inner in ast.walk(node)
        ):
            count += 1
    return count


def _n7_swallowed_failures(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N7: a try/except placed around the assertion, swallowing the failure."""
    added = _handlers_around_asserts(post) - _handlers_around_asserts(pre)
    if added <= 0:
        return []
    return [
        Finding(
            "N7",
            f"patch wraps {added} assertion(s) in exception handling; a caught "
            "AssertionError is a deleted test",
        )
    ]


def _test_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    }


def _n8_decollected_tests(pre: ast.AST, post: ast.AST) -> list[Finding]:
    """N8: a test skipped, xfailed, or renamed so pytest stops collecting it."""
    findings = []
    skipped_before = set(_decorator_targets(pre, SKIP_DECORATORS))
    skipped_after = set(_decorator_targets(post, SKIP_DECORATORS))
    added_skips = sorted(skipped_after - skipped_before)
    if added_skips:
        findings.append(
            Finding("N8", f"patch skips or xfails {', '.join(repr(n) for n in added_skips)}")
        )
    removed = sorted(_test_names(pre) - _test_names(post))
    if removed:
        findings.append(
            Finding(
                "N8",
                f"patch removes or renames test(s) out of collection: "
                f"{', '.join(repr(n) for n in removed)}",
            )
        )
    return findings
