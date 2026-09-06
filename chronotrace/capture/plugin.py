"""pytest plugin: paired trace capture and forced-ordering installation.

Registered through the ``pytest11`` entry point, so ``pytest --chronotrace``
works in any environment where ChronoTrace is installed. The plugin does three
things and nothing else:

* installs a :class:`~chronotrace.capture.instrument.Recorder` for the call
  phase and writes one :class:`~chronotrace.contracts.TraceCapture` per test;
* installs a :class:`~chronotrace.schedule.harness.ScheduleHarness` when the
  verifier asks for a forced ordering, and writes the harness state back out so
  an unreachable ordering (INFEASIBLE) is distinguishable from a failing test;
* pins the determinism knobs a reproducible replay needs (§21.5).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from chronotrace.capture import fingerprint as fingerprint_mod
from chronotrace.capture.instrument import Recorder, install_recorder
from chronotrace.contracts import TraceCapture
from chronotrace.schedule import determinism
from chronotrace.schedule.harness import ScheduleHarness, force_order

if TYPE_CHECKING:
    from collections.abc import Generator

_STASH_RECORDER = pytest.StashKey[Recorder]()
_STASH_HARNESS = pytest.StashKey[ScheduleHarness]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register ChronoTrace's command-line options."""
    group = parser.getgroup("chronotrace")
    group.addoption("--chronotrace", action="store_true", help="capture ChronoTrace spans")
    group.addoption(
        "--chronotrace-out",
        default=".chronotrace/traces",
        help="directory to write TraceCapture JSON into",
    )
    group.addoption(
        "--chronotrace-force",
        default=None,
        help="path to a JSON file describing the ordering to force",
    )
    group.addoption(
        "--chronotrace-seed", type=int, default=None, help="seed for the determinism controls"
    )
    group.addoption(
        "--chronotrace-pct",
        type=int,
        default=None,
        help="run under PCT-scheduled interleavings with this seed (verification tier 2)",
    )


def _force_spec(config: pytest.Config) -> dict[str, Any] | None:
    path = config.getoption("--chronotrace-force")
    if not path:
        return None
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def pytest_configure(config: pytest.Config) -> None:
    """Pin determinism controls before any test runs (§21.5)."""
    seed = config.getoption("--chronotrace-seed")
    if seed is not None:
        determinism.pin(seed)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, None, None]:
    """Install the recorder and any forced ordering around the test body."""
    config = item.config
    recorder = Recorder() if config.getoption("--chronotrace") else None
    spec = _force_spec(config)
    harness: ScheduleHarness | None = None
    if spec is not None and spec.get("test_id", item.nodeid) in (item.nodeid, "*"):
        harness = ScheduleHarness(
            order=list(spec["order"]),
            timeout_s=float(spec.get("gate_timeout_s", 5.0)),
        )
    if recorder is not None:
        item.stash[_STASH_RECORDER] = recorder
    if harness is not None:
        item.stash[_STASH_HARNESS] = harness
    with install_recorder(recorder), force_order(harness):
        yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, None, None]:
    """Write the trace capture and harness state once the call phase is decided."""
    outcome = yield
    if call.when != "call":
        return
    report = outcome.get_result()  # type: ignore[attr-defined]
    out_dir = Path(item.config.getoption("--chronotrace-out"))
    harness = item.stash.get(_STASH_HARNESS, None)
    if harness is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        state = harness.state()
        state["test_id"] = item.nodeid
        state["outcome"] = "PASS" if report.passed else "FAIL"
        (out_dir / "harness_state.json").write_text(json.dumps(state, indent=2))
    recorder = item.stash.get(_STASH_RECORDER, None)
    if recorder is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    capture = TraceCapture(
        run_id=uuid.uuid4().hex[:12],
        outcome="PASS" if report.passed else "FAIL",
        fingerprint=fingerprint_mod.compute(item.nodeid),
        spans=recorder.spans,
        complete=call.excinfo is None or not isinstance(call.excinfo.value, TimeoutError),
        instrumented=True,
        failure_message=str(report.longrepr) if report.failed else None,
        failing_resource=recorder.failing_resource,
    )
    name = f"{capture.outcome.lower()}-{capture.run_id}.json"
    (out_dir / name).write_text(capture.model_dump_json(indent=2))
    if os.environ.get("CHRONOTRACE_DEBUG"):
        print(f"chronotrace: wrote {out_dir / name}")
