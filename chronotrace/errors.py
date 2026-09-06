"""Typed exceptions.

Every failure path in ChronoTrace has a name, because the difference between an
infrastructure failure and a test failure is load-bearing (V3): an OOM-killed
container is not a flake, and a timeout is a deadlock signal, not a red test.
"""

from __future__ import annotations


class ChronoTraceError(Exception):
    """Base class for every ChronoTrace failure."""


class ConfigurationError(ChronoTraceError):
    """Settings are missing or contradictory."""


class CaptureError(ChronoTraceError):
    """A trace could not be captured or is unusable."""


class NoTracePairError(CaptureError):
    """The capture budget was exhausted without observing both a pass and a fail (E1)."""


class FingerprintMismatchError(CaptureError):
    """Two traces were captured in environments that are not comparable (E2)."""


class DiagnosisError(ChronoTraceError):
    """The diagnosis stage could not run to completion."""


class ScheduleError(ChronoTraceError):
    """The forced scheduler could not be installed or run."""


class InfeasibleOrderingError(ScheduleError):
    """The requested ordering could not be reached; the candidate is unreachable (Tier 1b)."""


class UnsupportedRuntimeError(ScheduleError):
    """The interpreter does not expose the internals the deterministic loop requires (§21.3)."""


class PatchError(ChronoTraceError):
    """A repair intent could not be applied deterministically."""


class GovernorRejectionError(ChronoTraceError):
    """A patch was rejected by the policy gate. Never caught to 'try harder' (INV-2)."""


class VerificationError(ChronoTraceError):
    """Verification infrastructure failed, as distinct from the test failing (V3)."""


class DeadlockDetectedError(VerificationError):
    """A verification run exceeded its wall-clock timeout (INV-4). Triggers rollback."""


class ProviderError(ChronoTraceError):
    """The model provider failed or returned something that is not a valid intent."""
