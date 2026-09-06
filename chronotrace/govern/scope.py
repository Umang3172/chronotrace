"""Scope rules: what a patch is allowed to touch (INV-6, INV-7, S2, S3).

Two distinct refusals live here. Third-party code is never patched at all.
Product code is never patched *silently* — a barrier injected into the product
to make a test green destroys real concurrency and can hide a genuine defect,
so it requires an explicit opt-in and is always reported.
"""

from __future__ import annotations

import ast
from pathlib import Path

from chronotrace.diagnose.graph import is_test_scope, is_third_party
from chronotrace.govern.negative import Finding

__all__ = ["check_scope"]


def check_scope(path: str, *, allow_production_repair: bool) -> list[Finding]:
    """Return scope violations for a file the patch would modify.

    Args:
        path: Path of the file being patched.
        allow_production_repair: Whether product-code edits were opted into.

    Returns:
        Findings for each scope rule violated.

    """
    findings: list[Finding] = []
    if is_third_party(path):
        findings.append(
            Finding("S3", f"{path} is installed or vendored dependency code and is never patched")
        )
    if not is_test_scope(path) and not allow_production_repair:
        findings.append(
            Finding(
                "S2",
                f"{path} is application code, not test code. Patching it to make a test "
                "green can hide a real product defect; pass --allow-production-repair to "
                "proceed deliberately",
            )
        )
    return findings


def parses(source: str, path: str) -> list[Finding]:
    """S4: the patched module must parse."""
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return [Finding("S4", f"patched {Path(path).name} does not parse: {exc}")]
    return []
