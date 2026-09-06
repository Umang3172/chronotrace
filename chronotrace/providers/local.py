"""Local provider: recorded-fixture replay over a deterministic reference policy.

**This is not a language model and must never be presented as one.** It is the
offline stand-in that keeps the pipeline, the benchmark and the eval harness
runnable with no credentials, and it makes fixture-replay demos reproducible at
zero cost.

Two consequences are enforced rather than documented and forgotten:

* Token and cost metrics are **not** produced here. A made-up token count is a
  fabricated metric, and the eval harness reports "n/a" for this provider rather
  than inventing one.
* Comparative arms A and B are refused by the eval harness on this provider,
  because a baseline drawn from a hand-written policy would say nothing about
  what a model does.

The selection rule itself is small and principled, which is the point: pattern
selection is the only judgement in the pipeline, and seeing how little of it
there is makes the deterministic remainder obvious.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from chronotrace.contracts import Diagnosis, OperationRef, RepairIntent
from chronotrace.errors import ProviderError
from chronotrace.logging import get_logger

log = get_logger(__name__)

__all__ = ["LocalModelProvider"]


class LocalModelProvider:
    """Deterministic reference policy with fixture recording and replay."""

    name = "local"

    def __init__(self, fixtures_dir: Path | None = None, *, replay_only: bool = False) -> None:
        """Create the provider.

        Args:
            fixtures_dir: Where (prompt, response) pairs are recorded so a run
                can be replayed offline and byte-identically later.
            replay_only: Refuse to synthesize a new response when no fixture
                exists. Used to prove a published result was replayed, not
                regenerated.

        """
        self.fixtures_dir = fixtures_dir
        self.replay_only = replay_only
        self._usage = (0, 0)
        self._calls = 0

    @property
    def last_usage(self) -> tuple[int, int]:
        """Always ``(0, 0)``: this provider has no tokens to report."""
        return self._usage

    @property
    def calls(self) -> int:
        """Number of ``propose`` calls made."""
        return self._calls

    def propose(self, diagnosis: Diagnosis, source: str) -> RepairIntent:
        """Select a repair pattern for a proven diagnosis.

        Args:
            diagnosis: A diagnosis whose status is RACE_PROVEN.
            source: Source of the module holding the racing operations, used
                only for the fixture key.

        Returns:
            The chosen typed intent.

        Raises:
            ProviderError: No fixture exists and ``replay_only`` is set.

        """
        self._calls += 1
        key = self._key(diagnosis, source)
        cached = self._load(key)
        if cached is not None:
            return cached
        if self.replay_only:
            raise ProviderError(
                f"no recorded fixture for {key}; refusing to synthesize in replay-only mode"
            )
        intent = self._select(diagnosis)
        self._store(key, diagnosis, intent)
        return intent

    def _select(self, diagnosis: Diagnosis) -> RepairIntent:
        inversion = diagnosis.proven_inversion
        if inversion is None or diagnosis.status != "RACE_PROVEN":
            return RepairIntent(
                transformation="NO_REPAIR",
                shared_scope="NONE",
                primitive="none",
                rationale="No causally sufficient ordering was proven, so no repair applies.",
            )
        first, second = inversion.op_a, inversion.op_b
        if _is_write(first) and _is_write(second):
            # Two independent producers writing the same resource. Ordering them
            # would serialise concurrency the code never promised; the assertion
            # is what over-constrains. Never auto-applied (P3, spec 19.9).
            return RepairIntent(
                transformation="RELAX_ASSERTION",
                shared_scope="NONE",
                signal_site=first,
                wait_site=second,
                primitive="none",
                rationale=(
                    f"{first.span_name} and {second.span_name} are independent writes to the "
                    "same state. Their order is not established by the code under test, so "
                    "the assertion over-constrains valid concurrency. Recommend relaxing the "
                    "assertion rather than synchronising; human review required."
                ),
            )
        # Read-after-write dependency: the reader observed state before the
        # writer published it. Signal on the write, wait on the read.
        writer = second if _is_write(second) else first
        reader = first if writer is second else second
        return RepairIntent(
            transformation="INJECT_ASYNC_EVENT",
            shared_scope="FIXTURE",
            scope_target=None,
            signal_site=writer,
            wait_site=reader,
            primitive="asyncio.Event",
            rationale=(
                f"{reader.span_name} read state that {writer.span_name} publishes. Forcing "
                "that order reproduced the failure every time, so the reader must wait for "
                "the writer to signal rather than assume it has already run."
            ),
        )

    def _key(self, diagnosis: Diagnosis, source: str) -> str:
        material = json.dumps(
            {"diagnosis": diagnosis.model_dump(mode="json"), "source": source}, sort_keys=True
        )
        return hashlib.sha256(material.encode()).hexdigest()[:20]

    def _path(self, key: str) -> Path | None:
        if self.fixtures_dir is None:
            return None
        return self.fixtures_dir / f"{key}.json"

    def _load(self, key: str) -> RepairIntent | None:
        path = self._path(key)
        if path is None or not path.exists():
            return None
        payload = json.loads(path.read_text())
        log.info("provider.fixture_replay", key=key)
        return RepairIntent.model_validate(payload["response"])

    def _store(self, key: str, diagnosis: Diagnosis, intent: RepairIntent) -> None:
        path = self._path(key)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "provider": self.name,
                    "request": {"diagnosis": diagnosis.model_dump(mode="json")},
                    "response": intent.model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
        )


def _is_write(ref: OperationRef) -> bool:
    """Return True when an operation writes the shared state it touches."""
    return ref.access == "write"
