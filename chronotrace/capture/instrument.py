"""Span emission at await boundaries, and the gate point the verifier reuses (A-4).

pytest emits no OpenTelemetry spans on its own, so the pipeline needs an
explicit instrumentation point. One decorator serves both roles that matter:

* it records an occurrence-indexed :class:`SpanRecord` (never name-keyed — D-3);
* it is the single place a forced-ordering gate can be applied (§21.2).

Instrumentation is inert when no recorder is installed, which is what makes the
probe-effect measurement (D3) possible: the same test binary runs instrumented
and uninstrumented.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator
from typing import ParamSpec, TypeVar

from chronotrace.contracts import SpanRecord
from chronotrace.schedule.harness import checkpoint

P = ParamSpec("P")
T = TypeVar("T")

__all__ = [
    "Recorder",
    "assertion",
    "current_recorder",
    "install_recorder",
    "operation",
    "reset_occurrences",
]


class Recorder:
    """Collects spans for a single test execution."""

    def __init__(self) -> None:
        """Create an empty recorder."""
        self.spans: list[SpanRecord] = []
        self._counters: dict[str, int] = {}
        self.failing_resource: str | None = None

    def next_occurrence(self, name: str) -> int:
        """Return and consume the next occurrence index for ``name`` (D-3)."""
        index = self._counters.get(name, 0)
        self._counters[name] = index + 1
        return index

    def add(self, span: SpanRecord) -> None:
        """Append a completed span."""
        self.spans.append(span)


_RECORDER: contextvars.ContextVar[Recorder | None] = contextvars.ContextVar(
    "chronotrace_recorder", default=None
)
_PARENT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "chronotrace_parent_span", default=None
)
_FALLBACK_COUNTERS: dict[str, int] = {}


def reset_occurrences() -> None:
    """Reset occurrence counters so operation keys restart at ``#0``.

    Occurrence indexes identify operations across runs (D-3), so they are per
    execution, not per process. The capture plugin calls this before every test;
    anything replaying a forced ordering in-process must call it too.
    """
    _FALLBACK_COUNTERS.clear()


def current_recorder() -> Recorder | None:
    """Return the recorder for the current run, if the plugin installed one."""
    return _RECORDER.get()


@contextlib.contextmanager
def install_recorder(recorder: Recorder | None) -> Iterator[Recorder | None]:
    """Install ``recorder`` for the duration of the block."""
    token = _RECORDER.set(recorder)
    reset_occurrences()
    try:
        yield recorder
    finally:
        _RECORDER.reset(token)


def _next_occurrence(name: str) -> int:
    recorder = _RECORDER.get()
    if recorder is not None:
        return recorder.next_occurrence(name)
    index = _FALLBACK_COUNTERS.get(name, 0)
    _FALLBACK_COUNTERS[name] = index + 1
    return index


def _task_name() -> str | None:
    import asyncio

    try:
        task = asyncio.current_task()
    except RuntimeError:
        return None
    return task.get_name() if task is not None else None


def operation(
    name: str,
    *,
    resource: str | None = None,
    access: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Instrument a coroutine function as a named, occurrence-indexed operation.

    Args:
        name: Operation name. Repeated calls are distinguished by occurrence.
        resource: Shared state this operation touches, used for resource-access
            edges in the observed-order graph and for the backward slice.
        access: ``"read"`` or ``"write"``.

    Returns:
        A decorator producing a coroutine function that gates on the active
        forced-ordering harness, then records a span around the original body.

    """

    def decorate(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        source_file = fn.__code__.co_filename
        source_line = fn.__code__.co_firstlineno

        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            occurrence = _next_occurrence(name)
            await checkpoint(f"{name}#{occurrence}")
            recorder = _RECORDER.get()
            if recorder is None:
                return await fn(*args, **kwargs)
            span_id = uuid.uuid4().hex[:16]
            parent = _PARENT.get()
            token = _PARENT.set(span_id)
            start = time.monotonic_ns()
            try:
                return await fn(*args, **kwargs)
            finally:
                _PARENT.reset(token)
                attributes: dict[str, str | int | float | bool] = {"ct.qualname": fn.__qualname__}
                if resource is not None:
                    attributes["ct.resource"] = resource
                if access is not None:
                    attributes["ct.access"] = access
                recorder.add(
                    SpanRecord(
                        span_id=span_id,
                        parent_span_id=parent,
                        name=name,
                        occurrence=occurrence,
                        start_ns=start,
                        end_ns=time.monotonic_ns(),
                        task_name=_task_name(),
                        source_file=source_file,
                        source_line=source_line,
                        attributes=attributes,
                    )
                )

        return wrapper

    return decorate


@contextlib.contextmanager
def assertion(resource: str, name: str = "assert") -> Iterator[None]:
    """Mark the assertion site and the state it reads.

    The backward slice (§9.1 stage 1) starts at the failed assertion, so the
    assertion's read set has to be observable. Recording it explicitly is more
    honest than guessing which span the assertion consumed.
    """
    recorder = _RECORDER.get()
    if recorder is None:
        yield
        return
    occurrence = recorder.next_occurrence(name)
    span_id = uuid.uuid4().hex[:16]
    parent = _PARENT.get()
    start = time.monotonic_ns()
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        recorder.failing_resource = resource
        raise
    finally:
        recorder.add(
            SpanRecord(
                span_id=span_id,
                parent_span_id=parent,
                name=name,
                occurrence=occurrence,
                start_ns=start,
                end_ns=time.monotonic_ns(),
                task_name=_task_name(),
                attributes={
                    "ct.resource": resource,
                    "ct.access": "read",
                    "ct.assertion": True,
                    "ct.failed": failed,
                },
            )
        )
