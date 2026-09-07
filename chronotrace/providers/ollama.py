"""Ollama provider — a local model, used for the three-arm baseline.

Two capabilities, because the experiment needs both halves of the comparison:

* :meth:`propose` returns a typed :class:`RepairIntent` and nothing else. This is
  the constrained path ChronoTrace uses (INV-1).
* :meth:`propose_patch` returns **source code**, which is what an unconstrained
  assistant produces. It exists only so the baseline arms can measure what a
  model does when nothing stops it. ChronoTrace never calls it.

**Thinking is suppressed.** qwen3 emits reasoning tokens by default, and they
corrupt structured output. ``think: false`` is sent on every request and the
response is checked for a populated ``thinking`` field, so a silent
reintroduction fails loudly rather than producing malformed intents.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from chronotrace.contracts import Diagnosis, RepairIntent
from chronotrace.errors import ProviderError
from chronotrace.logging import get_logger
from chronotrace.providers.record import CallRecord, FixtureRecorder

log = get_logger(__name__)

__all__ = ["OllamaProvider"]

_INTENT_SYSTEM = """You select a repair pattern for a proven asyncio race in a test.

You never write source code. You return one structured intent describing which
transformation to apply and where; deterministic tooling applies it and a policy
gate decides whether it may run at all.

Forbidden as repairs, and rejected automatically if proposed: sleeps of any
kind, retry loops or decorators, timeout inflation, weakened or deleted
assertions, skips. If the correct answer is that the assertion over-constrains
legitimate concurrency, say so with RELAX_ASSERTION rather than synchronising
two operations that are allowed to interleave. If no repair is appropriate,
return NO_REPAIR."""

_PATCH_SYSTEM = """You are a senior Python engineer fixing a failing test.

Return the complete corrected contents of the file, and nothing else. No
explanation, no markdown fences, no commentary — just the file."""


class OllamaProvider:
    """Calls a local Ollama model over HTTP."""

    name = "ollama"

    def __init__(
        self,
        *,
        host: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        temperature: float = 0.0,
        seed: int = 1729,
        max_tokens: int = 4096,
        timeout_s: float = 600.0,
        recorder: FixtureRecorder | None = None,
    ) -> None:
        """Configure the endpoint and the sampling parameters shared by every arm."""
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.recorder = recorder
        self._usage = (0, 0)
        self._totals = [0, 0]
        self._calls = 0
        self.context: dict[str, str] = {}
        """Arm and case labels attached to recorded calls."""

    # ------------------------------------------------------------------ #
    # ModelProvider protocol
    # ------------------------------------------------------------------ #

    @property
    def last_usage(self) -> tuple[int, int]:
        """Input and output tokens for the most recent call."""
        return self._usage

    @property
    def totals(self) -> tuple[int, int]:
        """Input and output tokens across every call this provider has made."""
        return (self._totals[0], self._totals[1])

    @property
    def calls(self) -> int:
        """Number of model calls made."""
        return self._calls

    def propose(self, diagnosis: Diagnosis, source: str) -> RepairIntent:
        """Ask for a typed repair intent (the constrained path).

        Args:
            diagnosis: The proven diagnosis, serialized as the model's evidence.
            source: Source of the module holding the racing operations.

        Returns:
            The validated intent.

        Raises:
            ProviderError: The model never returned a valid intent.

        """
        payload = json.dumps(
            {"diagnosis": diagnosis.model_dump(mode="json"), "source": source},
            indent=2,
            sort_keys=True,
        )
        raw = self._chat(
            system=_INTENT_SYSTEM,
            user=payload,
            schema=RepairIntent.model_json_schema(),
            schema_name="RepairIntent",
        )
        try:
            return RepairIntent.model_validate_json(raw)
        except Exception as exc:
            raise ProviderError(f"model returned an invalid RepairIntent: {exc}") from exc

    def propose_patch(self, *, system_extra: str, user: str) -> str:
        """Ask for a rewritten source file (the unconstrained baseline path).

        Args:
            system_extra: Arm-specific addition to the system prompt.
            user: The full user prompt for this arm.

        Returns:
            The model's raw response, expected to be file contents.

        """
        system = _PATCH_SYSTEM + (f"\n\n{system_extra}" if system_extra else "")
        return self._chat(system=system, user=user, schema=None, schema_name="source_file")

    # ------------------------------------------------------------------ #
    # transport
    # ------------------------------------------------------------------ #

    def _chat(
        self, *, system: str, user: str, schema: dict[str, Any] | None, schema_name: str
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_predict": self.max_tokens,
            },
        }
        if schema is not None:
            body["format"] = schema
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"ollama request failed: {exc}") from exc

        message = data.get("message", {})
        if message.get("thinking"):
            raise ProviderError(
                "the model returned reasoning tokens despite think=false; structured "
                "output cannot be trusted. Fix thinking suppression before continuing."
            )
        content = str(message.get("content", ""))
        tokens_in = int(data.get("prompt_eval_count", 0))
        tokens_out = int(data.get("eval_count", 0))
        self._usage = (tokens_in, tokens_out)
        self._totals[0] += tokens_in
        self._totals[1] += tokens_out
        self._calls += 1
        elapsed = time.monotonic() - started
        log.info(
            "ollama.call",
            schema=schema_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            seconds=round(elapsed, 1),
            **self.context,
        )
        if self.recorder is not None:
            self.recorder.record(
                CallRecord(
                    provider=f"{self.name}:{self.model}",
                    system=system,
                    user=user,
                    schema_name=schema_name,
                    response=content,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    seconds=round(elapsed, 3),
                    arm=self.context.get("arm", ""),
                    case_id=self.context.get("case", ""),
                    attempt=int(self.context.get("attempt", "1")),
                )
            )
        if not content.strip():
            raise ProviderError("model returned an empty response")
        return content
