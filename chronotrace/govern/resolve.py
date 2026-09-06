"""Import resolution for policy checks (N2, G-4).

Matching banned constructs on name text is how a governor gets bypassed:
``from time import sleep as s`` defeats a check for ``time.sleep``, and
``"timeout" in decorator_name`` false-positives on anything containing the
word. Every check therefore resolves names to fully qualified targets through
the module's own imports before comparing.
"""

from __future__ import annotations

import ast

__all__ = ["ImportTable", "build_table"]


class ImportTable:
    """Maps local names to the fully qualified symbols they refer to."""

    def __init__(self) -> None:
        """Create an empty table."""
        self.aliases: dict[str, str] = {}

    def resolve(self, node: ast.expr) -> str | None:
        """Return the fully qualified name a call target refers to, if known."""
        dotted = _dotted(node)
        if dotted is None:
            return None
        head, _, tail = dotted.partition(".")
        base = self.aliases.get(head)
        if base is None:
            return dotted
        return f"{base}.{tail}" if tail else base

    def resolves_to(self, node: ast.expr, targets: set[str]) -> bool:
        """Return True when ``node`` refers to one of ``targets``."""
        resolved = self.resolve(node)
        return resolved is not None and resolved in targets


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return None


def build_table(tree: ast.AST) -> ImportTable:
    """Build the import table for a parsed module."""
    table = ImportTable()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                table.aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                table.aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return table
