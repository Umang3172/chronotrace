"""The LibCST transformer: cross-scope injection and the edge cases the draft got wrong."""

import ast

import pytest

from chronotrace.contracts import OperationRef, RepairIntent
from chronotrace.errors import PatchError
from chronotrace.synthesize.apply import apply_intent

MODULE = '''"""A module docstring that must survive."""

import asyncio

import pytest

STORE = {}


async def preselect_value():
    """A decoy whose name contains 'select'."""
    return None


async def select_value():
    """Read the stored value."""
    return STORE.get("v")


async def commit_value(value):
    """Write the stored value."""
    STORE["v"] = value  # a comment that must survive


@pytest.mark.asyncio
async def test_reader():
    assert await select_value() == 1
'''


def _ref(name, *, access, line):
    return OperationRef(
        span_name=name,
        occurrence=0,
        source_file="tests/test_m.py",
        source_line=line,
        qualname=name,
        is_test_scope=True,
        access=access,
        resource="store.v",
    )


def _intent(**overrides):
    base = {
        "transformation": "INJECT_ASYNC_EVENT",
        "shared_scope": "FIXTURE",
        "primitive": "asyncio.Event",
        "signal_site": _ref("commit_value", access="write", line=22),
        "wait_site": _ref("select_value", access="read", line=17),
        "rationale": "test",
    }
    return RepairIntent(**{**base, **overrides})


def test_injects_into_two_different_functions():
    """P-3: a race is between two coroutines, so one function is never enough."""
    patch = apply_intent(MODULE, _intent(), path="tests/test_m.py", is_test_module=True)
    tree = ast.parse(patch.patched)
    functions = {
        node.name: ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
    }
    assert ".set()" in functions["commit_value"]
    assert ".wait()" in functions["select_value"]


def test_wait_is_inserted_after_the_docstring():
    """P-4: prepending before a docstring destroys it."""
    patch = apply_intent(MODULE, _intent(), path="tests/test_m.py", is_test_module=True)
    tree = ast.parse(patch.patched)
    target = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "select_value"
    )
    assert ast.get_docstring(target) == "Read the stored value."
    assert isinstance(target.body[1], ast.Expr)


def test_module_docstring_and_comments_survive():
    patch = apply_intent(MODULE, _intent(), path="tests/test_m.py", is_test_module=True)
    assert ast.get_docstring(ast.parse(patch.patched)) == "A module docstring that must survive."
    assert "# a comment that must survive" in patch.patched


def test_decoy_function_with_a_matching_substring_is_untouched():
    """P-2: 'select' must not match 'preselect'."""
    patch = apply_intent(MODULE, _intent(), path="tests/test_m.py", is_test_module=True)
    tree = ast.parse(patch.patched)
    decoy = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "preselect_value"
    )
    assert len(decoy.body) == 2  # docstring plus the original return


def test_fixture_scope_recreates_the_primitive_per_test():
    """asyncio primitives bind to a loop; pytest builds a new loop per test."""
    patch = apply_intent(MODULE, _intent(), path="tests/test_m.py", is_test_module=True)
    assert patch.scope_applied == "FIXTURE"
    assert "autouse=True" in patch.patched
    assert "asyncio.Event()" in patch.patched.split("autouse=True")[1]


def test_non_test_module_falls_back_to_module_scope():
    patch = apply_intent(MODULE, _intent(), path="app/service.py", is_test_module=False)
    assert patch.scope_applied == "MODULE"
    assert "autouse=True" not in patch.patched


def test_same_function_for_both_sites_is_refused():
    """An event set and awaited in one coroutine is a no-op, not a repair."""
    intent = _intent(wait_site=_ref("commit_value", access="read", line=22))
    with pytest.raises(PatchError, match="same function"):
        apply_intent(MODULE, intent, path="tests/test_m.py", is_test_module=True)


def test_missing_site_is_refused_rather_than_guessed():
    intent = _intent(signal_site=_ref("no_such_function", access="write", line=1))
    with pytest.raises(PatchError, match="not found"):
        apply_intent(MODULE, intent, path="tests/test_m.py", is_test_module=True)


def test_patched_module_still_parses():
    """S4, checked here too so a malformed emission fails fast."""
    patch = apply_intent(MODULE, _intent(), path="tests/test_m.py", is_test_module=True)
    ast.parse(patch.patched)
    assert patch.diff.startswith("--- a/tests/test_m.py")


def test_await_unfinished_task_moves_the_await_above_the_assertion():
    source = (
        "import asyncio\n\n\n"
        "async def test_x():\n"
        "    handle = asyncio.create_task(worker())\n"
        "    assert value() == 1\n"
        "    await handle\n"
    )
    intent = RepairIntent(
        transformation="AWAIT_UNFINISHED_TASK",
        shared_scope="NONE",
        scope_target="handle",
        primitive="task_await",
        rationale="test",
    )
    patch = apply_intent(source, intent, path="tests/test_m.py", is_test_module=True)
    lines = [line.strip() for line in patch.patched.splitlines() if line.strip()]
    assert lines.index("await handle") < lines.index("assert value() == 1")
    assert lines.count("await handle") == 1


def test_transformations_without_a_patch_are_refused_explicitly():
    for transformation in ("RELAX_ASSERTION", "NO_REPAIR"):
        intent = _intent(transformation=transformation)
        with pytest.raises(PatchError, match="no patch"):
            apply_intent(MODULE, intent, path="tests/test_m.py", is_test_module=True)
