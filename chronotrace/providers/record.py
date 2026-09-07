"""Model-call recording and replay.

Every call is written to disk with everything needed to replay it: both prompts,
the schema asked for, the raw response, token counts, and which arm and case it
belonged to. That is what lets a reader reproduce a published number with no
credentials, no local model and no GPU.

Keys identify *which call* was made — provider, arm, case, attempt — and
deliberately do **not** hash the prompt. The prompt embeds run-dependent
evidence (the observed flake rate, the captured traceback), so hashing it would
mean a replay could never find its own recording. The prompt is still stored and
compared on replay, and any difference is reported as drift rather than hidden.

A missing fixture is an error, never a silent regeneration — otherwise
"replayed" would quietly mean "re-ran".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from chronotrace.errors import ProviderError

__all__ = ["CallRecord", "FixtureProvider", "FixtureRecorder", "fixture_key"]


@dataclass(frozen=True)
class CallRecord:
    """One model call, in full."""

    provider: str
    system: str
    user: str
    schema_name: str
    response: str
    tokens_input: int
    tokens_output: int
    seconds: float
    arm: str
    case_id: str
    attempt: int

    @property
    def key(self) -> str:
        """Deterministic identity for this call."""
        return fixture_key(
            provider=self.provider,
            arm=self.arm,
            case_id=self.case_id,
            attempt=self.attempt,
        )


def fixture_key(*, provider: str, arm: str, case_id: str, attempt: int) -> str:
    """Return the fixture key identifying one call in one arm of one case."""
    material = json.dumps(
        {"provider": provider, "arm": arm, "case": case_id, "attempt": attempt},
        sort_keys=True,
    )
    return hashlib.sha256(material.encode()).hexdigest()[:24]


class FixtureRecorder:
    """Writes call records into a directory, one JSON file per call."""

    def __init__(self, directory: Path) -> None:
        """Create the recorder, making the directory if needed."""
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.written = 0

    def record(self, call: CallRecord) -> Path:
        """Write one call and return the file it landed in."""
        path = self.directory / f"{call.key}.json"
        path.write_text(json.dumps(asdict(call), indent=2, sort_keys=True))
        self.written += 1
        return path

    def load(self, key: str) -> CallRecord | None:
        """Return a recorded call by key, or None when it was never recorded."""
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        return CallRecord(**json.loads(path.read_text()))

    def count(self) -> int:
        """Return the number of fixtures currently on disk."""
        return len(list(self.directory.glob("*.json")))


class FixtureProvider:
    """Replays recorded calls. Never contacts a model.

    A judge reproducing the published numbers runs with this provider. If a
    fixture is missing the run fails, because a replay that quietly falls back to
    a live model is not a replay.
    """

    name = "fixture"

    def __init__(self, directory: Path, *, provider_label: str) -> None:
        """Replay calls recorded from ``provider_label``."""
        self.recorder = FixtureRecorder(directory)
        self.provider_label = provider_label
        self._usage = (0, 0)
        self._totals = [0, 0]
        self._calls = 0
        self.context: dict[str, str] = {}
        self.prompt_drift: list[str] = []
        """Calls whose prompt differed from the recording. Reported, not hidden."""

    @property
    def last_usage(self) -> tuple[int, int]:
        """Input and output tokens of the replayed call."""
        return self._usage

    @property
    def totals(self) -> tuple[int, int]:
        """Input and output tokens across every replayed call."""
        return (self._totals[0], self._totals[1])

    @property
    def calls(self) -> int:
        """Number of calls replayed."""
        return self._calls

    def replay(self, *, system: str, user: str) -> str:
        """Return the recorded response for a call, or fail loudly."""
        arm = self.context.get("arm", "")
        case_id = self.context.get("case", "")
        key = fixture_key(
            provider=self.provider_label,
            arm=arm,
            case_id=case_id,
            attempt=int(self.context.get("attempt", "1")),
        )
        record = self.recorder.load(key)
        if record is None:
            raise ProviderError(
                f"no recorded call for {key} (arm={arm}, case={case_id}); refusing to "
                "contact a model in replay mode"
            )
        if record.system != system or record.user != user:
            self.prompt_drift.append(f"{arm}/{case_id}")
        self._usage = (record.tokens_input, record.tokens_output)
        self._totals[0] += record.tokens_input
        self._totals[1] += record.tokens_output
        self._calls += 1
        return record.response

    def propose(self, diagnosis: object, source: str) -> object:
        """Replay a typed-intent call."""
        from chronotrace.contracts import Diagnosis, RepairIntent
        from chronotrace.providers.ollama import _INTENT_SYSTEM

        assert isinstance(diagnosis, Diagnosis)
        payload = json.dumps(
            {"diagnosis": diagnosis.model_dump(mode="json"), "source": source},
            indent=2,
            sort_keys=True,
        )
        raw = self.replay(system=_INTENT_SYSTEM, user=payload)
        return RepairIntent.model_validate_json(raw)

    def propose_patch(self, *, system_extra: str, user: str) -> str:
        """Replay a source-rewriting call."""
        from chronotrace.providers.ollama import _PATCH_SYSTEM

        system = _PATCH_SYSTEM + (f"\n\n{system_extra}" if system_extra else "")
        return self.replay(system=system, user=user)
