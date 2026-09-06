"""ChronoTrace — repairs concurrency-induced flaky asyncio tests.

The public surface is deliberately small. Three things are worth importing from
here: the data contracts every stage speaks in, the pipeline that runs a repair
end to end, and the forced-ordering harness that makes the causal claim
testable.

Everything else is a stage, reachable from its own package.
"""

from __future__ import annotations

from chronotrace.contracts import (
    CandidateInversion,
    CaptureBundle,
    Diagnosis,
    ExecutionFingerprint,
    GovernorVerdict,
    IncidentReport,
    OperationRef,
    RepairIntent,
    RuleOutcome,
    SpanRecord,
    TraceCapture,
    VerificationResult,
)
from chronotrace.errors import (
    ChronoTraceError,
    DeadlockDetectedError,
    GovernorRejectionError,
    InfeasibleOrderingError,
    NoTracePairError,
    PatchError,
)
from chronotrace.pipeline import repair
from chronotrace.schedule.harness import ScheduleHarness, force_order

__version__ = "0.1.0"

__all__ = [
    "CandidateInversion",
    "CaptureBundle",
    "ChronoTraceError",
    "DeadlockDetectedError",
    "Diagnosis",
    "ExecutionFingerprint",
    "GovernorRejectionError",
    "GovernorVerdict",
    "IncidentReport",
    "InfeasibleOrderingError",
    "NoTracePairError",
    "OperationRef",
    "PatchError",
    "RepairIntent",
    "RuleOutcome",
    "ScheduleHarness",
    "SpanRecord",
    "TraceCapture",
    "VerificationResult",
    "__version__",
    "force_order",
    "repair",
]
