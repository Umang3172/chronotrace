"""Deterministic patch application via LibCST (P-1..P-5).

The model never writes source (INV-1). It returns a typed intent, and this
module turns that intent into a syntax tree edit that preserves the file's
existing formatting and comments.

Four things the draft spec got wrong, and how they are avoided here:

* **P-1** — statements are inserted into ``IndentedBlock.body``, which takes
  ``BaseStatement``. ``parse_statement`` returns exactly that, so the
  small-statement/statement type mismatch cannot arise.
* **P-2** — functions are matched by qualified name against the operation
  reference, never by substring against source text. ``select`` does not match
  ``preselect``, and neither matches a comment.
* **P-3** — a race is *by definition* between two different coroutines, so the
  primitive is created in shared scope and the signal and wait are injected into
  two different functions.
* **P-4** — insertion is after a docstring, never before it.

**P-5** does not arise: the supported paradigm is asyncio only (spec 19.1), so
the primitive family is fixed. Threading and multiprocessing are refused during
diagnosis rather than mis-patched here.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import libcst as cst
import libcst.matchers as m

from chronotrace.contracts import OperationRef, RepairIntent
from chronotrace.errors import PatchError

__all__ = ["AppliedPatch", "apply_intent", "unified_diff"]


@dataclass
class AppliedPatch:
    """The result of applying one intent to one module."""

    path: str
    original: str
    patched: str
    primitive_name: str
    scope_applied: str
    signal_function: str
    wait_function: str

    @property
    def diff(self) -> str:
        """Unified diff between the original and patched source."""
        return unified_diff(self.original, self.patched, self.path)


def unified_diff(before: str, after: str, path: str) -> str:
    """Return a unified diff between two versions of a file."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def gate_name(intent: RepairIntent) -> str:
    """Return a deterministic name for the injected primitive."""
    seed = intent.signal_site.resource if intent.signal_site else None
    seed = seed or (intent.signal_site.span_name if intent.signal_site else "gate")
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", seed).strip("_").lower()
    return f"_chronotrace_gate_{slug}"


def apply_intent(
    source: str, intent: RepairIntent, *, path: str, is_test_module: bool
) -> AppliedPatch:
    """Apply a repair intent to a module's source.

    Args:
        source: The module's current source.
        intent: The typed intent to apply.
        path: Path of the module, used for the diff header.
        is_test_module: Whether a pytest fixture may be emitted into this module.

    Returns:
        The applied patch, including both versions of the source.

    Raises:
        PatchError: The intent is not applicable, or names sites this module
            does not contain.

    """
    if intent.transformation == "INJECT_ASYNC_EVENT":
        return _inject_async_event(source, intent, path=path, is_test_module=is_test_module)
    if intent.transformation == "AWAIT_UNFINISHED_TASK":
        return _await_unfinished_task(source, intent, path=path)
    raise PatchError(
        f"transformation {intent.transformation!r} produces no patch; it is either an "
        "abstention or a recommendation for human review"
    )


# --------------------------------------------------------------------------- #
# INJECT_ASYNC_EVENT
# --------------------------------------------------------------------------- #


def _inject_async_event(
    source: str, intent: RepairIntent, *, path: str, is_test_module: bool
) -> AppliedPatch:
    if intent.signal_site is None or intent.wait_site is None:
        raise PatchError("INJECT_ASYNC_EVENT requires both a signal site and a wait site")
    if intent.signal_site.source_file != intent.wait_site.source_file:
        raise PatchError(
            "signal and wait sites live in different modules; cross-module shared scope "
            "is not supported"
        )
    if intent.signal_site.qualname == intent.wait_site.qualname:
        raise PatchError(
            "signal and wait sites are the same function; a race is between two "
            "coroutines, so an event there would be a no-op (P-3)"
        )
    name = gate_name(intent)
    scope = "FIXTURE" if (intent.shared_scope == "FIXTURE" and is_test_module) else "MODULE"
    module = cst.parse_module(source)
    transformer = _EventInjector(
        gate=name,
        signal=intent.signal_site,
        wait=intent.wait_site,
        emit_fixture=scope == "FIXTURE",
    )
    patched = module.visit(transformer)
    if not transformer.signal_applied:
        raise PatchError(f"signal site {intent.signal_site.qualname!r} not found in {path}")
    if not transformer.wait_applied:
        raise PatchError(f"wait site {intent.wait_site.qualname!r} not found in {path}")
    return AppliedPatch(
        path=path,
        original=source,
        patched=patched.code,
        primitive_name=name,
        scope_applied=scope,
        signal_function=intent.signal_site.qualname,
        wait_function=intent.wait_site.qualname,
    )


class _EventInjector(cst.CSTTransformer):
    """Creates the event in shared scope and injects set/wait into two functions."""

    def __init__(
        self, *, gate: str, signal: OperationRef, wait: OperationRef, emit_fixture: bool
    ) -> None:
        """Configure the injection sites."""
        super().__init__()
        self.gate = gate
        self.signal = signal
        self.wait = wait
        self.emit_fixture = emit_fixture
        self.signal_applied = False
        self.wait_applied = False
        self._scope: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._scope.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        self._scope.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self._scope.append(node.name.value)
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        qualname = ".".join(self._scope)
        self._scope.pop()
        if _matches(qualname, self.signal):
            self.signal_applied = True
            return _append_statement(updated_node, f"{self.gate}.set()")
        if _matches(qualname, self.wait):
            self.wait_applied = True
            return _prepend_statement(updated_node, f"await {self.gate}.wait()")
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        body: list[Any] = list(updated_node.body)
        if not _imports(updated_node, "asyncio"):
            body.insert(_import_anchor(body), cst.parse_statement("import asyncio\n"))
        declaration = cst.parse_statement(f"{self.gate} = asyncio.Event()\n").with_changes(
            leading_lines=[cst.EmptyLine()]
        )
        insert_at = _last_import_index(body) + 1
        body.insert(insert_at, declaration)
        if self.emit_fixture:
            if not _imports(updated_node, "pytest"):
                body.insert(_import_anchor(body), cst.parse_statement("import pytest\n"))
                insert_at += 1
            body.insert(insert_at + 1, _reset_fixture(self.gate))
            body = _pad_after(body, insert_at + 1)
        return updated_node.with_changes(body=body)


def _pad_after(body: list[Any], index: int) -> list[Any]:
    """Restore blank-line separation after an inserted block-level definition."""
    following = index + 1
    if following >= len(body):
        return body
    node = body[following]
    leading = getattr(node, "leading_lines", None)
    if leading is None:
        return body
    missing = max(0, 2 - len(leading))
    padded = node.with_changes(leading_lines=[*([cst.EmptyLine()] * missing), *leading])
    return [*body[:following], padded, *body[following + 1 :]]


def _reset_fixture(gate: str) -> cst.BaseStatement:
    """Build the autouse fixture that gives each test a fresh gate.

    The gate is **recreated**, not cleared. asyncio synchronization primitives
    bind to the event loop they are first awaited on, and pytest-asyncio builds
    a new loop per test, so a module-level event reused across tests raises
    "bound to a different event loop" on the second one. Clearing it would leave
    that defect in place and the repair would appear to stop holding.

    Managing the primitive's lifetime from a fixture is what ``FIXTURE`` shared
    scope means here (P-3).
    """
    code = (
        f"\n\n@pytest.fixture(autouse=True)\n"
        f"def _chronotrace_reset{gate[len('_chronotrace_gate') :]}():\n"
        f'    """Provide a fresh synchronization gate for each test."""\n'
        f"    global {gate}\n"
        f"    {gate} = asyncio.Event()\n"
        f"    yield\n"
    )
    return cst.parse_statement(code.lstrip("\n")).with_changes(
        leading_lines=[cst.EmptyLine(), cst.EmptyLine()]
    )


# --------------------------------------------------------------------------- #
# AWAIT_UNFINISHED_TASK
# --------------------------------------------------------------------------- #


def _await_unfinished_task(source: str, intent: RepairIntent, *, path: str) -> AppliedPatch:
    variable = intent.scope_target
    if not variable:
        raise PatchError("AWAIT_UNFINISHED_TASK requires the task variable in scope_target")
    module = cst.parse_module(source)
    transformer = _TaskAwaiter(variable=variable)
    patched = module.visit(transformer)
    if not transformer.applied:
        raise PatchError(f"no function creates a task named {variable!r} followed by an assertion")
    return AppliedPatch(
        path=path,
        original=source,
        patched=patched.code,
        primitive_name=variable,
        scope_applied="NONE",
        signal_function=transformer.function or "",
        wait_function=transformer.function or "",
    )


class _TaskAwaiter(cst.CSTTransformer):
    """Moves the await of an already-created task above the assertion it guards."""

    def __init__(self, *, variable: str) -> None:
        """Configure the task variable to await."""
        super().__init__()
        self.variable = variable
        self.applied = False
        self.function: str | None = None

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if self.applied or not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node
        statements = list(updated_node.body.body)
        if not any(_creates_task(item, self.variable) for item in statements):
            return updated_node
        assertion_at = next(
            (index for index, item in enumerate(statements) if _is_assertion(item)), None
        )
        if assertion_at is None:
            return updated_node
        statements = [
            item
            for index, item in enumerate(statements)
            if not (index > assertion_at and _is_bare_await(item, self.variable))
        ]
        statements.insert(assertion_at, cst.parse_statement(f"await {self.variable}\n"))
        self.applied = True
        self.function = updated_node.name.value
        return updated_node.with_changes(body=updated_node.body.with_changes(body=statements))


def _creates_task(statement: cst.BaseStatement, variable: str) -> bool:
    return m.matches(
        statement,
        m.SimpleStatementLine(
            body=[
                m.Assign(
                    targets=[m.AssignTarget(target=m.Name(value=variable))],
                    value=m.Call(func=m.Attribute(attr=m.Name(value="create_task"))),
                )
            ]
        ),
    )


def _is_assertion(statement: cst.BaseStatement) -> bool:
    if m.matches(statement, m.SimpleStatementLine(body=[m.Assert()])):
        return True
    return m.matches(
        statement, m.With(items=[m.WithItem(item=m.Call(func=m.Name(value="assertion")))])
    )


def _is_bare_await(statement: cst.BaseStatement, variable: str) -> bool:
    return m.matches(
        statement,
        m.SimpleStatementLine(body=[m.Expr(value=m.Await(expression=m.Name(value=variable)))]),
    )


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #


def _matches(qualname: str, ref: OperationRef) -> bool:
    """Match a function by qualified name against an operation reference (P-2)."""
    return qualname == ref.qualname or qualname.split(".")[-1] == ref.qualname.split(".")[-1]


def _has_docstring(node: cst.FunctionDef) -> bool:
    block = node.body
    if not isinstance(block, cst.IndentedBlock) or not block.body:
        return False
    return m.matches(block.body[0], m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())]))


def _prepend_statement(node: cst.FunctionDef, code: str) -> cst.FunctionDef:
    """Insert a statement at the top of a function body, after any docstring (P-4)."""
    block = node.body
    if not isinstance(block, cst.IndentedBlock):
        raise PatchError(f"cannot patch single-line function {node.name.value!r}")
    statements = list(block.body)
    statements.insert(1 if _has_docstring(node) else 0, cst.parse_statement(f"{code}\n"))
    return node.with_changes(body=block.with_changes(body=statements))


def _append_statement(node: cst.FunctionDef, code: str) -> cst.FunctionDef:
    """Insert a statement at the end of a function body."""
    block = node.body
    if not isinstance(block, cst.IndentedBlock):
        raise PatchError(f"cannot patch single-line function {node.name.value!r}")
    return node.with_changes(
        body=block.with_changes(body=[*block.body, cst.parse_statement(f"{code}\n")])
    )


def _imports(module: cst.Module, name: str) -> bool:
    for statement in module.body:
        if m.matches(statement, m.SimpleStatementLine(body=[m.Import()])):
            line = cst.ensure_type(statement, cst.SimpleStatementLine)
            imp = cst.ensure_type(line.body[0], cst.Import)
            for alias in imp.names:
                if m.matches(alias.name, m.Name(value=name)):
                    return True
    return False


def _import_anchor(body: Sequence[Any]) -> int:
    """Return the index to insert an import at: after a module docstring."""
    if body and m.matches(body[0], m.SimpleStatementLine(body=[m.Expr(value=m.SimpleString())])):
        return 1
    return 0


def _last_import_index(body: Sequence[Any]) -> int:
    last = _import_anchor(body) - 1
    for index, statement in enumerate(body):
        if m.matches(statement, m.SimpleStatementLine(body=[m.Import()])) or m.matches(
            statement, m.SimpleStatementLine(body=[m.ImportFrom()])
        ):
            last = index
    return last
