"""Test execution: one process per run, per-run results, hard timeouts.

Three rules this module exists to enforce:

* **Never use ``returncode`` as a pass count** (V-1). ``pytest-json-report``
  gives per-test outcomes; a return code collapses 99-of-100-passing to a
  boolean and destroys the flakiness metric.
* **One process per run** (V-3). Shared-fixture and dirty-read flakiness need
  real isolation to reproduce, and module-level state from a previous repeat
  would silently change the next one.
* **Every subprocess has a wall-clock timeout** (INV-4). A timeout is a
  deadlock signal that triggers rollback, not a failing test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from chronotrace.contracts import TraceCapture
from chronotrace.errors import VerificationError
from chronotrace.logging import get_logger

log = get_logger(__name__)

__all__ = ["RunOutcome", "run_test"]


@dataclass
class RunOutcome:
    """The result of a single test execution."""

    passed: bool
    timed_out: bool
    duration_s: float
    """Wall-clock duration of the whole run, including process startup."""
    test_duration_s: float = 0.0
    """Duration of the test call phase alone, from the per-run JSON report."""
    infeasible: bool = False
    """The forced ordering could not be reached (Tier 1b), which is not a failure."""
    harness_state: dict[str, object] | None = None
    capture: TraceCapture | None = None
    stdout: str = ""
    stderr: str = ""
    collected: bool = True
    """False when pytest never ran the test — infrastructure failure, not a flake (V3)."""
    metadata: dict[str, str] = field(default_factory=dict)


def _pytest_argv(
    test_id: str,
    report_path: Path,
    *,
    capture_dir: Path | None,
    force_path: Path | None,
    seed: int | None,
    pct_seed: int | None,
) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "pytest",
        test_id,
        "-q",
        "-p",
        "no:cacheprovider",
        "--json-report",
        f"--json-report-file={report_path}",
    ]
    if capture_dir is not None:
        argv += ["--chronotrace", "--chronotrace-out", str(capture_dir)]
    if force_path is not None:
        argv += ["--chronotrace-force", str(force_path)]
    if seed is not None:
        argv += ["--chronotrace-seed", str(seed)]
    if pct_seed is not None:
        argv += ["--chronotrace-pct", str(pct_seed)]
    return argv


def _read_report(report_path: Path) -> tuple[bool, bool, float]:
    """Return ``(passed, collected, call_duration)`` from a pytest-json-report file (V-1).

    Per-test outcomes come from the report, never from the process return code:
    a return code collapses 99-of-100-passing to a boolean and destroys the
    flakiness metric entirely.
    """
    if not report_path.exists():
        return False, False, 0.0
    data = json.loads(report_path.read_text())
    tests = data.get("tests", [])
    if not tests:
        return False, False, 0.0
    passed = all(test.get("outcome") == "passed" for test in tests)
    duration = sum(float(test.get("call", {}).get("duration", 0.0)) for test in tests)
    return passed, True, duration


def _read_capture(capture_dir: Path) -> TraceCapture | None:
    files = sorted(capture_dir.glob("*-*.json"))
    for path in files:
        if path.name == "harness_state.json":
            continue
        return TraceCapture.model_validate_json(path.read_text())
    return None


def run_test(
    test_id: str,
    *,
    cwd: Path,
    timeout_s: float,
    capture: bool = False,
    force: dict[str, object] | None = None,
    seed: int | None = None,
    pct_seed: int | None = None,
    hash_seed: str = "0",
    isolation: str = "process",
) -> RunOutcome:
    """Run one test once, in its own process.

    Args:
        test_id: A pytest node id.
        cwd: Repository root to run in.
        timeout_s: Wall-clock cap. Exceeding it is reported as a deadlock signal.
        capture: Emit ChronoTrace spans and return the :class:`TraceCapture`.
        force: Forced-ordering specification, or None for a natural run.
        seed: Seed for the determinism controls. ``None`` leaves the run
            natural, which is what the statistical tier needs — pinning seeds
            there would make "N/N stable" trivially true.
        pct_seed: Seed for PCT-scheduled execution (Tier 2). ``None`` runs on
            the ordinary event loop.
        hash_seed: ``PYTHONHASHSEED`` for the child process.
        isolation: ``"process"`` or ``"docker"``.

    Returns:
        The outcome, distinguishing pass, fail, timeout and infeasible ordering.

    """
    with tempfile.TemporaryDirectory(prefix="chronotrace-run-") as tmp:
        tmp_path = Path(tmp)
        report_path = tmp_path / "report.json"
        capture_dir = tmp_path / "capture"
        capture_dir.mkdir()
        force_path: Path | None = None
        if force is not None:
            force_path = tmp_path / "force.json"
            force_path.write_text(json.dumps(force))
        argv = _pytest_argv(
            test_id,
            report_path,
            capture_dir=capture_dir if capture else None,
            force_path=force_path,
            seed=seed,
            pct_seed=pct_seed,
        )
        if force is not None and not capture:
            argv += ["--chronotrace-out", str(capture_dir)]
        env = dict(os.environ, PYTHONHASHSEED=hash_seed)
        if isolation == "docker":
            argv = _dockerize(argv, cwd)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            log.warning("run.timeout", test_id=test_id, timeout_s=timeout_s)
            return RunOutcome(
                passed=False,
                timed_out=True,
                duration_s=time.monotonic() - started,
                metadata={"isolation": isolation},
            )
        except OSError as exc:  # docker missing, interpreter missing
            raise VerificationError(f"could not launch test run: {exc}") from exc
        duration = time.monotonic() - started
        passed, collected, call_duration = _read_report(report_path)
        harness_state: dict[str, object] | None = None
        state_path = capture_dir / "harness_state.json"
        if state_path.exists():
            harness_state = json.loads(state_path.read_text())
        return RunOutcome(
            passed=passed,
            timed_out=False,
            duration_s=duration,
            test_duration_s=call_duration,
            infeasible=bool(harness_state and harness_state.get("infeasible")),
            harness_state=harness_state,
            capture=_read_capture(capture_dir) if capture else None,
            stdout=completed.stdout[-4000:],
            stderr=completed.stderr[-4000:],
            collected=collected,
            metadata={"isolation": isolation, "run_id": uuid.uuid4().hex[:8]},
        )


def _dockerize(argv: list[str], cwd: Path) -> list[str]:
    """Wrap ``argv`` so it executes inside a container (V-2, V-3)."""
    image = os.environ.get("CHRONOTRACE_IMAGE", "chronotrace-runner:latest")
    return [
        "docker",
        "run",
        "--rm",
        "--cpus",
        os.environ.get("CHRONOTRACE_CPUS", "1"),
        "-v",
        f"{cwd}:/app",
        "-w",
        "/app",
        "-e",
        "PYTHONHASHSEED",
        image,
        *argv[1:],
    ]
