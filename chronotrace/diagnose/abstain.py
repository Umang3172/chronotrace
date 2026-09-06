"""Abstention checks — every reason ChronoTrace refuses to answer (INV-5).

Abstention is a first-class outcome, not a failure. The trace diff will always
find *some* inversion, so a system that always returns an answer will
confidently patch noise, and a wrong patch to a test is worse than no patch at
all. Each function here is one documented refusal path; none of them may be
weakened to improve a repair-rate number.
"""

from __future__ import annotations

import ast
from pathlib import Path

from chronotrace.contracts import TraceCapture

__all__ = [
    "assertion_failed",
    "detect_paradigm",
    "nondeterministic_sources",
    "test_file_of",
]

_NONDETERMINISTIC_MODULES = {"random", "secrets", "uuid", "time", "datetime", "socket"}
_NONDETERMINISTIC_CALLS = {
    "random": "unseeded random number generation",
    "uuid4": "random identifier generation",
    "now": "wall-clock time",
    "today": "wall-clock date",
    "time": "wall-clock time",
    "urandom": "operating system entropy",
}


def test_file_of(test_id: str) -> Path:
    """Return the file part of a pytest node id."""
    return Path(test_id.split("::", 1)[0])


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return None


def detect_paradigm(path: Path) -> str:
    """Classify the concurrency paradigm a test module uses.

    ChronoTrace supports asyncio only (spec 19.1): the event loop's ready queue
    is the only tractable forced-scheduling control point in CPython. Threading
    and multiprocessing are detected so the system can refuse them, never so it
    can repair them.

    Returns:
        ``"asyncio"``, ``"threading"``, ``"multiprocessing"`` or ``"unknown"``.

    """
    tree = _parse(path)
    if tree is None:
        return "unknown"
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    if "multiprocessing" in modules:
        return "multiprocessing"
    if "threading" in modules or "concurrent" in modules:
        return "threading"
    if "asyncio" in modules or "anyio" in modules:
        return "asyncio"
    return "unknown"


def nondeterministic_sources(path: Path) -> list[str]:
    """Return plain-language descriptions of non-schedule nondeterminism in a module.

    Used only when no inversion was found: it distinguishes "the schedule is not
    the variable" (D1, abstain as NOT_A_RACE) from "we could not see the
    schedule" (D2).
    """
    tree = _parse(path)
    if tree is None:
        return []
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _NONDETERMINISTIC_MODULES:
                    found[root] = f"module {root!r} imported"
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in _NONDETERMINISTIC_MODULES:
                found[root] = f"module {root!r} imported"
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in _NONDETERMINISTIC_CALLS:
                found[name] = _NONDETERMINISTIC_CALLS[name]
    return [found[key] for key in sorted(found)]


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def assertion_failed(capture: TraceCapture) -> bool:
    """Return True when the run failed at an instrumented assertion.

    A failure that never reached an assertion — an upstream call raising, a
    fixture erroring — is not evidence about shared state, and treating it as a
    race would be fabrication.
    """
    for span in capture.spans:
        if span.attributes.get("ct.assertion") and span.attributes.get("ct.failed"):
            return True
    return False
