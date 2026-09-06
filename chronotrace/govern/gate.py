"""The policy gate (INV-2).

Every patch passes through here before it is applied, and the gate cannot be
bypassed, weakened, or relaxed "just for the demo" — it is the entire
differentiator. It is both **negative** (rejects sleeps, retries, timeout
inflation, weakened assertions) and **positive** (confirms a real
synchronization primitive was actually added, reachable from both sides).

The verdict names every rule it evaluated, passed or failed, so the report can
show the whole gauntlet rather than only the rule that fired.
"""

from __future__ import annotations

from chronotrace.contracts import GovernorVerdict, RuleOutcome
from chronotrace.govern import deadlock, negative, positive, scope
from chronotrace.govern.negative import Finding
from chronotrace.logging import get_logger

log = get_logger(__name__)

__all__ = ["RULES", "review"]

RULES: dict[str, str] = {
    "N1": "no sleep calls introduced",
    "N2": "no aliased sleep imports introduced",
    "N3": "no timeout marker added or inflated",
    "N4": "no retry or flaky decorator added",
    "N5": "no retry loop wrapped around the assertion",
    "N6": "no assertion removed or weakened",
    "N7": "no exception handler swallowing the failure",
    "N8": "no test skipped, xfailed or renamed out of collection",
    "P1": "a real synchronization primitive was added",
    "P2": "the primitive is reachable from both the signal and the wait site",
    "P3": "the patch is not a no-op",
    "S1": "the proposed wait edge creates no wait-for cycle",
    "S2": "no production-scope file modified without opt-in",
    "S3": "no third-party or vendored file modified",
    "S4": "the patched module parses",
}

DIFF_RULES = {"N3", "N6", "N8"}
"""Rules that cannot be decided from the post-patch tree alone (G-3)."""


def review(
    *,
    before: str,
    after: str,
    path: str,
    allow_production_repair: bool = False,
) -> GovernorVerdict:
    """Evaluate every policy rule against a proposed patch.

    Args:
        before: Source before the patch.
        after: Source after the patch.
        path: Path of the file the patch modifies.
        allow_production_repair: Whether product-code edits were opted into.

    Returns:
        The verdict, with one outcome per rule in :data:`RULES`.

    """
    findings: list[Finding] = []
    findings += scope.parses(after, path)
    if any(finding.rule_id == "S4" for finding in findings):
        return _verdict(findings)

    findings += negative.check_negative(before, after)
    findings += positive.check_positive(before, after)
    findings += scope.check_scope(path, allow_production_repair=allow_production_repair)

    cycle = deadlock.find_cycle(after)
    if cycle is not None:
        findings.append(
            Finding(
                "S1",
                "the proposed wait edge closes a cycle in the wait-for graph "
                f"({' -> '.join(cycle)}); applying it would turn an intermittent "
                "failure into a permanent hang",
            )
        )
    verdict = _verdict(findings)
    log.info(
        "governor.verdict",
        approved=verdict.approved,
        violations=[finding.rule_id for finding in findings],
    )
    return verdict


def _verdict(findings: list[Finding]) -> GovernorVerdict:
    failed = {finding.rule_id: finding.detail for finding in findings}
    outcomes = [
        RuleOutcome(
            rule_id=rule_id,
            description=description,
            passed=rule_id not in failed,
            detail=failed.get(rule_id, ""),
        )
        for rule_id, description in RULES.items()
    ]
    negatives = [
        f"{finding.rule_id}: {finding.detail}"
        for finding in findings
        if finding.rule_id.startswith("N")
    ]
    return GovernorVerdict(
        approved=not findings,
        negative_violations=negatives,
        positive_check_passed=not any(finding.rule_id.startswith("P") for finding in findings),
        deadlock_cycle_detected=any(finding.rule_id == "S1" for finding in findings),
        scope_violation=any(finding.rule_id in {"S2", "S3"} for finding in findings),
        diff_checks=[
            f"{finding.rule_id}: {finding.detail}"
            for finding in findings
            if finding.rule_id in DIFF_RULES
        ],
        rules_evaluated=outcomes,
    )
