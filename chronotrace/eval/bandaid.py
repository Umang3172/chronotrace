"""Band-aid scanning for the baseline arms.

Detection reuses the governor's own negative rules verbatim. Writing a second,
looser detector for the baseline would make the comparison meaningless — the
three arms have to be judged by identical rules, and the rules that judge them
are the rules that gate ChronoTrace's own patches.

The one thing added here is measuring *how much* delay a band-aid costs, which
the governor never needs to know because it rejects the patch outright.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from chronotrace.govern.negative import SLEEP_TARGETS, check_negative
from chronotrace.govern.resolve import build_table

__all__ = ["BandAidScan", "scan"]


@dataclass
class BandAidScan:
    """What a patch introduced, judged by the governor's rules."""

    findings: list[tuple[str, str]] = field(default_factory=list)
    sleep_seconds: float = 0.0
    parse_error: str | None = None

    @property
    def is_band_aid(self) -> bool:
        """True when the patch introduces any banned construct."""
        return bool(self.findings)

    @property
    def rule_ids(self) -> list[str]:
        """Distinct rule ids violated, in rule order."""
        return sorted({rule for rule, _ in self.findings})

    @property
    def summary(self) -> str:
        """One-line description of what the patch did."""
        if self.parse_error:
            return f"unparseable: {self.parse_error}"
        if not self.findings:
            return "none"
        return "; ".join(f"{rule}: {detail}" for rule, detail in self.findings)


def scan(before: str, after: str) -> BandAidScan:
    """Scan a patch for band-aid constructs and measure the delay it adds.

    Args:
        before: Source before the patch.
        after: Source after the patch.

    Returns:
        The scan, including seconds of fixed delay introduced.

    """
    try:
        pre_tree = ast.parse(before)
        post_tree = ast.parse(after)
    except SyntaxError as exc:
        return BandAidScan(parse_error=str(exc))
    findings = [(f.rule_id, f.detail) for f in check_negative(before, after)]
    return BandAidScan(
        findings=findings,
        sleep_seconds=_sleep_seconds(post_tree) - _sleep_seconds(pre_tree),
    )


def _sleep_seconds(tree: ast.AST) -> float:
    """Sum the constant durations of every sleep call in a module.

    A sleep with a computed or variable duration contributes nothing to the
    total, so the reported CI cost is a *lower bound* rather than an estimate.
    """
    table = build_table(tree)
    total = 0.0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not table.resolves_to(node.func, SLEEP_TARGETS):
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, int | float) and not isinstance(value, bool):
                total += float(value)
    return total
