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

    def propose(
        self, diagnosis: Diagnosis, source: str, previous_error: str | None = None
    ) -> RepairIntent:
        """Return a repair intent for a proven diagnosis.

        Args:
            diagnosis: The proven diagnosis.
            source: Source of the module holding the racing operations.
            previous_error: Validation error from the preceding attempt, shown
                to the model so it can correct a malformed intent.

        """
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


@runtime_checkable
class BaselineProvider(Protocol):
    """A provider that can also write source code.

    Only the baseline arms use ``propose_patch``. ChronoTrace itself never calls
    it — INV-1 says the model emits typed intents and nothing else — but
    measuring what an unconstrained model does requires letting one write code.
    """

    name: str
    context: dict[str, str]

    def propose(
        self, diagnosis: Diagnosis, source: str, previous_error: str | None = None
    ) -> RepairIntent:
        """Return a typed repair intent, optionally correcting a prior attempt."""
        ...

    def propose_patch(self, *, system_extra: str, user: str) -> str:
        """Return rewritten source for a file."""
        ...

    @property
    def last_usage(self) -> tuple[int, int]:
        """Return ``(input_tokens, output_tokens)`` for the most recent call."""
        ...

    @property
    def totals(self) -> tuple[int, int]:
        """Return cumulative ``(input_tokens, output_tokens)``."""
        ...

    @property
    def calls(self) -> int:
        """Return the number of model calls made so far."""
        ...
