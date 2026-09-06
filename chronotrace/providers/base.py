"""Provider protocols (spec 33).

Everything except the final Bedrock swap is buildable and fully evaluable with
zero AWS access, and the eval harness must never require a network. Two
protocols is all the indirection that needs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from chronotrace.contracts import Diagnosis, IncidentReport, RepairIntent


@runtime_checkable
class ModelProvider(Protocol):
    """Selects a repair pattern and emits a typed intent. Never source code (INV-1)."""

    name: str

    def propose(self, diagnosis: Diagnosis, source: str) -> RepairIntent:
        """Return a repair intent for a proven diagnosis."""
        ...

    @property
    def last_usage(self) -> tuple[int, int]:
        """Return ``(input_tokens, output_tokens)`` for the most recent call."""
        ...

    @property
    def calls(self) -> int:
        """Return the number of model calls made so far."""
        ...


@runtime_checkable
class TelemetrySink(Protocol):
    """Persists incident reports for audit and post-mortem."""

    def emit(self, report: IncidentReport) -> None:
        """Write one report to the sink."""
        ...
