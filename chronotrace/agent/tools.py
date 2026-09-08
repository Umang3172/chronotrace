"""Tools the agent loop can call (spec 19.4).

Agentic depth here is multi-step *tool use*, not a second model. The loop can
ask for a trace slice, compare candidate orderings, force a specific one, read
source context and request verification — and then decide to repair, investigate
further, or abstain.

Authority stays deterministic throughout. The loop can request a forced replay;
it cannot decide that a rejected patch is acceptable, and it cannot write source.

Every argument and return value is primitive JSON. Raw spans and CST nodes in
agent state are how an AgentCore runtime ends up serializing an object into a
fallback string representation and blowing past its payload limit (E4).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from chronotrace.capture.collect import collect
from chronotrace.contracts import CaptureBundle, Diagnosis
from chronotrace.diagnose.depth import ConfirmationBudget, confirm
from chronotrace.diagnose.engine import diagnose
from chronotrace.diagnose.graph import build
from chronotrace.diagnose.rank import candidates as rank_candidates
from chronotrace.diagnose.slice import backward_slice
from chronotrace.govern.gate import review
from chronotrace.verify.runner import run_test

__all__ = ["AgentTools"]

_F = TypeVar("_F", bound=Callable[..., Any])

try:
    from strands import tool
except ImportError:  # pragma: no cover - optional dependency

    def tool(func: _F) -> _F:  # type: ignore[no-redef]
        """Identity stand-in so this module imports without the optional SDK.

        The tool surface is plain Python and stays callable either way; only the
        Strands registration is lost, and the only caller that needs it already
        raises a clear error when the SDK is missing.
        """
        return func


class AgentTools:
    """Stateful tool surface bound to one incident."""

    def __init__(self, test_id: str, cwd: Path, *, timeout_s: float = 30.0) -> None:
        """Bind the tools to a test and a repository root."""
        self.test_id = test_id
        self.cwd = cwd
        self.timeout_s = timeout_s
        self._bundle: CaptureBundle | None = None
        self._diagnosis: Diagnosis | None = None

    @tool
    def capture_traces(self, runs: int = 20) -> dict[str, Any]:
        """Run the test repeatedly and gather a comparable pass/fail trace pair.

        Args:
            runs: Maximum runs to spend.

        Returns:
            Counts, the measured flake rate, and whether a usable pair exists.

        """
        self._bundle = collect(self.test_id, cwd=self.cwd, runs=runs, timeout_s=self.timeout_s)
        return {
            "runs_executed": self._bundle.runs_executed,
            "passing": len(self._bundle.passing),
            "failing": len(self._bundle.failing),
            "flake_rate": round(self._bundle.natural_flake_rate, 3),
            "has_comparable_pair": self._bundle.has_pair,
        }

    @tool
    def trace_slice(self) -> dict[str, Any]:
        """Return the operations the failed assertion could have depended on.

        Returns:
            The backward slice: operation keys, their resources and access
            directions.

        """
        bundle = self._require_bundle()
        graphs = [build(capture) for capture in bundle.failing + bundle.passing]
        failing_resource = bundle.failing[0].failing_resource
        sliced, resources = backward_slice(graphs, failing_resource)
        operations = []
        for key in sorted(sliced):
            for graph in graphs:
                if key in graph.spans:
                    operations.append(
                        {
                            "operation": key,
                            "resource": graph.resource_of(key),
                            "access": graph.access_of(key),
                            "source_line": graph.spans[key].source_line,
                        }
                    )
                    break
        return {
            "failing_resource": failing_resource,
            "resources_in_slice": sorted(resources),
            "operations": operations,
        }

    @tool
    def compare_orderings(self) -> dict[str, Any]:
        """Rank the orderings that differ between passing and failing runs.

        Returns:
            Candidates, best first, with suspiciousness and slice membership.

        """
        bundle = self._require_bundle()
        graphs = [build(capture) for capture in bundle.failing + bundle.passing]
        sliced, _ = backward_slice(graphs, bundle.failing[0].failing_resource)
        found = rank_candidates(bundle.passing, bundle.failing, sliced)
        return {
            "candidates": [
                {
                    "order": candidate.failing_order,
                    "suspiciousness": candidate.ochiai_score,
                    "in_backward_slice": candidate.in_backward_slice,
                    "causal_position": candidate.causal_position,
                    "classification": candidate.classification,
                }
                for candidate in found
            ]
        }

    @tool
    def force_replay(self, order: list[str], runs: int = 5) -> dict[str, Any]:
        """Force one ordering and report what happened.

        This is the tool that turns a ranking into a decision: a rate of 1.0
        means the ordering is a sufficient condition for the failure.

        Args:
            order: Operation keys in the order to force.
            runs: How many times to run under that ordering.

        Returns:
            The forced failure rate and the resulting classification.

        """
        bundle = self._require_bundle()
        graphs = [build(capture) for capture in bundle.failing + bundle.passing]
        sliced, _ = backward_slice(graphs, bundle.failing[0].failing_resource)
        found = [
            candidate
            for candidate in rank_candidates(bundle.passing, bundle.failing, sliced)
            if candidate.failing_order == order
        ]
        if not found:
            return {"error": f"{order} is not an observed inversion", "classification": None}
        classified, deadlock = confirm(
            found,
            test_id=self.test_id,
            cwd=self.cwd,
            budget=ConfirmationBudget(candidates=1, runs=runs),
            timeout_s=self.timeout_s,
        )
        candidate = classified[0]
        return {
            "order": order,
            "forced_failure_rate": candidate.forced_failure_rate,
            "classification": candidate.classification,
            "deadlock_detected": deadlock,
        }

    @tool
    def source_context(self, path: str, line: int, window: int = 12) -> dict[str, Any]:
        """Return source around a line, so the loop can see what it is deciding about.

        Args:
            path: Repository-relative file path.
            line: 1-indexed line number.
            window: Lines of context either side.

        Returns:
            The numbered source window.

        """
        target = self.cwd / path
        if not target.exists():
            return {"error": f"{path} does not exist"}
        lines = target.read_text().splitlines()
        start = max(0, line - window)
        end = min(len(lines), line + window)
        return {
            "path": path,
            "start_line": start + 1,
            "source": "\n".join(
                f"{number:>4} {text}"
                for number, text in enumerate(lines[start:end], start=start + 1)
            ),
        }

    @tool
    def diagnose_now(self) -> dict[str, Any]:
        """Run the full diagnosis and return its decided status.

        Returns:
            Status, abstention reason if any, and the plain-language explanation.

        """
        bundle = self._require_bundle()
        self._diagnosis = diagnose(bundle, cwd=self.cwd, timeout_s=self.timeout_s)
        return {
            "status": self._diagnosis.status,
            "abstain_reason": self._diagnosis.abstain_reason,
            "explanation": self._diagnosis.explanation,
            "bug_depth": self._diagnosis.bug_depth,
        }

    @tool
    def check_patch(self, before: str, after: str, path: str) -> dict[str, Any]:
        """Ask the governor whether a patch would be allowed to run.

        The loop may call this; it may not overrule the answer.

        Args:
            before: Source before the patch.
            after: Source after the patch.
            path: File the patch modifies.

        Returns:
            The verdict and every rule that failed, with reasons.

        """
        verdict = review(before=before, after=after, path=path)
        return {
            "approved": verdict.approved,
            "violations": [
                {"rule": rule.rule_id, "why": rule.detail}
                for rule in verdict.rules_evaluated
                if not rule.passed
            ],
        }

    @tool
    def run_once(self) -> dict[str, Any]:
        """Run the test once under natural conditions.

        Returns:
            Whether it passed, how long it took, and whether it timed out.

        """
        outcome = run_test(self.test_id, cwd=self.cwd, timeout_s=self.timeout_s)
        return {
            "passed": outcome.passed,
            "timed_out": outcome.timed_out,
            "duration_s": round(outcome.duration_s, 3),
        }

    def _require_bundle(self) -> CaptureBundle:
        if self._bundle is None or not self._bundle.has_pair:
            self.capture_traces()  # type: ignore[call-arg]
        if self._bundle is None or not self._bundle.has_pair:
            message = "no comparable pass/fail trace pair; diagnosis must abstain (E1)"
            raise RuntimeError(message)
        return self._bundle
