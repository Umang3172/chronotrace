"""Data contracts shared by every ChronoTrace module (spec §22).

This module exists because the pipeline crosses four process boundaries (pytest
subprocess, agent loop, verifier, UI) and one model boundary. A single set of
pydantic models is what keeps those boundaries honest: every stage validates its
input rather than trusting the stage before it.

All state that reaches the agent must be JSON-serializable primitives (E4), so
nothing here holds raw OpenTelemetry spans, CST nodes or callables.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #


class ExecutionFingerprint(BaseModel):
    """Identity of the environment a trace was captured in.

    Two traces are comparable only if their fingerprints match exactly (E2).
    "Same commit" is necessary but not sufficient — a Python or dependency
    difference is an environmental explanation for divergence, not a race.
    """

    commit_sha: str
    python_version: str
    dependency_lock_hash: str
    container_image: str
    test_id: str
    env_hash: str


class SpanRecord(BaseModel):
    """One observed operation in one execution.

    Attributes:
        occurrence: The nth span with this name in this run. Spans are never
            keyed by name alone (D-3) — a loop emitting fifty ``SELECT`` spans
            would collapse to one entry.

    """

    span_id: str
    parent_span_id: str | None = None
    name: str
    occurrence: int
    start_ns: int
    end_ns: int
    task_name: str | None = None
    source_file: str | None = None
    source_line: int | None = None
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @property
    def key(self) -> str:
        """Occurrence-indexed identity, stable across runs (D-3)."""
        return f"{self.name}#{self.occurrence}"


class TraceCapture(BaseModel):
    """All spans emitted by a single test execution, plus its outcome."""

    run_id: str
    outcome: Literal["PASS", "FAIL"]
    fingerprint: ExecutionFingerprint
    spans: list[SpanRecord] = Field(default_factory=list)
    complete: bool = True
    """False if the run crashed or hung before spans were flushed (D4)."""
    instrumented: bool = True
    """False for uninstrumented baseline runs, used to measure probe effect (D3)."""
    failure_message: str | None = None
    failing_resource: str | None = None
    """Resource read by the failed assertion; the root of the backward slice."""


class CaptureBundle(BaseModel):
    """The paired traces one test yielded, plus what the capture stage measured.

    The pipeline requires a comparable pass/fail pair (E1). When the budget is
    exhausted without one, this bundle says so and diagnosis abstains rather
    than reasoning from a single trace.
    """

    test_id: str
    passing: list[TraceCapture] = Field(default_factory=list)
    failing: list[TraceCapture] = Field(default_factory=list)
    runs_executed: int = 0
    runs_timed_out: int = 0
    natural_flake_rate: float = 0.0
    uninstrumented_flake_rate: float | None = None
    """Flake rate without span emission. The delta is the probe effect (D3)."""
    fingerprint_conflicts: int = 0
    """Runs discarded because their environment was not comparable (E2)."""

    @property
    def has_pair(self) -> bool:
        """True when both a passing and a failing trace were observed."""
        return bool(self.passing) and bool(self.failing)

    @property
    def probe_effect_delta(self) -> float | None:
        """Instrumented minus uninstrumented flake rate, or None if unmeasured."""
        if self.uninstrumented_flake_rate is None:
            return None
        return self.natural_flake_rate - self.uninstrumented_flake_rate


# --------------------------------------------------------------------------- #
# diagnosis
# --------------------------------------------------------------------------- #


class OperationRef(BaseModel):
    """Stable identity for an operation.

    Matching is by structured identity, never by substring against source text
    (P-2): ``select`` must not match ``preselect``.
    """

    span_name: str
    occurrence: int
    source_file: str
    source_line: int
    qualname: str
    is_test_scope: bool
    """False means production code — drives D8 / INV-7 scope reporting."""
    access: Literal["read", "write", "unknown"] = "unknown"
    """Direction of the shared-state access, from capture-time instrumentation."""
    resource: str | None = None
    """The shared state this operation touches."""

    @property
    def key(self) -> str:
        """Occurrence-indexed identity, matching :attr:`SpanRecord.key`."""
        return f"{self.span_name}#{self.occurrence}"


class CandidateInversion(BaseModel):
    """A pair of operations observed in one order when passing and the other when failing."""

    op_a: OperationRef
    op_b: OperationRef
    causal_position: int
    """Index of the earliest involved span. Candidates rank earliest-first (D-7)."""
    ochiai_score: float
    in_backward_slice: bool
    classification: Literal[
        "UNTESTED",
        "IRRELEVANT",
        "SUSPICIOUS",
        "NECESSARY_INSUFFICIENT",
        "CAUSALLY_SUFFICIENT",
        "INFEASIBLE",
    ] = "UNTESTED"
    forced_failure_rate: float | None = None
    """None until the ordering has been forced. Drives ``classification`` (§13)."""
    failing_order: list[str] = Field(default_factory=list)
    """Operation keys in the order observed in failing runs, earliest first."""


class Diagnosis(BaseModel):
    """The outcome of the diagnosis stage. Abstention is a first-class result (INV-5)."""

    status: Literal["RACE_PROVEN", "NEEDS_INVESTIGATION", "ABSTAINED"]
    abstain_reason: (
        Literal[
            "NOT_A_RACE",
            "NO_INVERSION",
            "DEPTH_GE_2_UNRESOLVED",
            "NO_TRACE_PAIR",
            "SPAN_GRANULARITY_TOO_COARSE",
            "PRODUCTION_SCOPE_RACE",
            "NON_ASYNCIO_PARADIGM",
            "THIRD_PARTY_CODE",
        ]
        | None
    ) = None
    proven_inversion: CandidateInversion | None = None
    bug_depth: int | None = None
    candidates_evaluated: int = 0
    candidates: list[CandidateInversion] = Field(default_factory=list)
    explanation: str = ""
    """Plain-language summary for the UI. Never the basis of a decision."""


# --------------------------------------------------------------------------- #
# synthesis — the only thing the model emits (INV-1)
# --------------------------------------------------------------------------- #


class RepairIntent(BaseModel):
    """A typed transformation request. The model emits this and nothing else (INV-1)."""

    transformation: Literal[
        "INJECT_ASYNC_EVENT",
        "AWAIT_UNFINISHED_TASK",
        "ISOLATE_FIXTURE_SCOPE",
        "RELAX_ASSERTION",
        "NO_REPAIR",
    ]
    shared_scope: Literal["FIXTURE", "CLASS_ATTR", "MODULE", "NONE"]
    scope_target: str | None = None
    signal_site: OperationRef | None = None
    wait_site: OperationRef | None = None
    primitive: Literal["asyncio.Event", "asyncio.Barrier", "task_await", "none"]
    rationale: str


# --------------------------------------------------------------------------- #
# governance
# --------------------------------------------------------------------------- #


class GovernorVerdict(BaseModel):
    """Result of the deterministic policy gate. No patch is applied without one."""

    approved: bool
    negative_violations: list[str] = Field(default_factory=list)
    positive_check_passed: bool = False
    deadlock_cycle_detected: bool = False
    scope_violation: bool = False
    diff_checks: list[str] = Field(default_factory=list)
    """Findings that require the pre/post diff rather than the post AST alone (G-3)."""
    rules_evaluated: list[RuleOutcome] = Field(default_factory=list)


class RuleOutcome(BaseModel):
    """Per-rule result, rendered as the governor gauntlet in the UI (§27)."""

    rule_id: str
    description: str
    passed: bool
    detail: str = ""


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #


class VerificationResult(BaseModel):
    """Evidence produced by the tiered verifier. ``tier_reached`` is never inflated."""

    tier_reached: Literal[
        "FORCED_HARMLESS",
        "FORCED_UNREACHABLE",
        "INFEASIBLE",
        "PCT",
        "STATISTICAL",
        "FAILED",
    ]
    """Tier 1 splits by *how* the patch defeated the ordering.

    ``FORCED_HARMLESS`` — the failing interleaving still occurs and no longer
    breaks the test. ``FORCED_UNREACHABLE`` — the patch made that interleaving
    impossible to produce at all, which is the stronger outcome. Both are
    repairs. Scoring only the first would quietly reward ChronoTrace's own
    transformation, which leaves the ordering reachable, over repairs that
    eliminate it.
    """
    pre_patch_forced_failed: bool | None = None
    post_patch_forced_passed: bool | None = None
    post_patch_forced_infeasible: bool | None = None
    """The forced ordering could no longer be produced after the patch."""
    pct_runs: int = 0
    pct_failures: int = 0
    statistical_runs: int = 0
    statistical_failures: int = 0
    pre_patch_natural_failures: int = 0
    """Failures in the same number of natural runs before the patch, for comparison."""
    deadlock_detected: bool = False
    measured_overhead_ms: float = 0.0
    """Measured, never assumed to be zero (§19.3)."""
    reproduction_seed: dict[str, str] = Field(default_factory=dict)
    isolation: Literal["process", "docker"] = "process"
    symptom_patch_suspected: bool = False
    """Tier 1 passed but Tier 3 still flaky — the signature of patching a symptom (§13)."""

    @property
    def causally_proven(self) -> bool:
        """True when forced replay failed pre-patch and the patch defeated it.

        Defeating it means either the ordering became harmless or it became
        unreachable. Both are proofs about the same experiment: the harness did
        not change between the two runs, so the patch is the only variable.
        """
        if self.pre_patch_forced_failed is not True:
            return False
        if self.tier_reached == "FORCED_HARMLESS":
            return self.post_patch_forced_passed is True
        if self.tier_reached == "FORCED_UNREACHABLE":
            return self.post_patch_forced_infeasible is True
        return False

    @property
    def repair_strength(self) -> str:
        """Plain-language strength of the repair, for reports and the UI."""
        if self.tier_reached == "FORCED_UNREACHABLE":
            return "the failing interleaving can no longer occur"
        if self.tier_reached == "FORCED_HARMLESS":
            return "the failing interleaving still occurs and is now harmless"
        return "not established"


# --------------------------------------------------------------------------- #
# presentation
# --------------------------------------------------------------------------- #


class LaneSpan(BaseModel):
    """One span placed on a shared time axis, for the trace divergence view.

    Times are relative to the first span of the run and expressed in
    milliseconds, so a passing and a failing execution can be drawn against one
    another without leaking absolute clocks into the UI.
    """

    key: str
    name: str
    start_ms: float
    duration_ms: float
    task_name: str | None = None
    source_line: int | None = None
    access: str | None = None
    in_inversion: bool = False
    is_assertion: bool = False


class TraceLane(BaseModel):
    """One execution rendered as a lane of spans."""

    outcome: Literal["PASS", "FAIL"]
    run_id: str
    total_ms: float
    spans: list[LaneSpan] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #


class IncidentReport(BaseModel):
    """Everything ChronoTrace produced for one flaky test. The unit the UI renders."""

    incident_id: str
    test_id: str
    ui_state: Literal["FIXED", "NEEDS_INVESTIGATION", "ABSTAINED"]
    diagnosis: Diagnosis
    intent: RepairIntent | None = None
    verdict: GovernorVerdict | None = None
    verification: VerificationResult | None = None
    unified_diff: str | None = None
    regression_test_path: str | None = None
    regression_verified: bool = False
    """The emitted guard was executed and reproduced the ordering it claims to."""
    natural_flake_rate: float = 0.0
    probe_effect_delta: float | None = None
    """Instrumented minus uninstrumented flake rate (D3). None when unmeasured."""
    pass_lane: TraceLane | None = None
    fail_lane: TraceLane | None = None
    """One representative execution each, for the divergence view."""
    rejected_attempts: list[GovernorVerdict] = Field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
    llm_calls: int = 0
    wall_clock_s: float = 0.0
    provider: str = "local"
    """Which ModelProvider produced the intent. Numbers from different providers never mix."""


IncidentReport.model_rebuild()
GovernorVerdict.model_rebuild()
