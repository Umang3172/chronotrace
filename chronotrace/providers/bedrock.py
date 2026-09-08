"""Amazon Bedrock provider.

The model is asked for one thing: a :class:`RepairIntent` matching a JSON
schema. It is given no ability to emit source, because source it emits could not
be checked the way a typed intent can (INV-1).

Model ids are **not hardcoded**. The drafted id in the original spec was already
stale, so the ids are configuration and an unset id is an error rather than a
silent fallback to something that may no longer exist in the region.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from chronotrace.contracts import Diagnosis, RepairIntent
from chronotrace.errors import ConfigurationError, ProviderError
from chronotrace.logging import get_logger
from chronotrace.providers.prompts import INTENT_SYSTEM

if TYPE_CHECKING:
    from chronotrace.config import Settings

log = get_logger(__name__)

__all__ = ["BedrockProvider"]


_TOOL_NAME = "emit_repair_intent"


DEFAULT_BEDROCK_MODEL = "amazon.nova-pro-v1:0"


class BedrockProvider:
    """Calls a Bedrock model and validates its response into a typed intent."""

    name = "bedrock"

    def __init__(self, settings: Settings) -> None:
        """Create a client for the configured region and model."""
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ConfigurationError(
                "the bedrock provider needs boto3: uv sync --extra bedrock"
            ) from exc
        self.settings = settings
        self.model_id = settings.model_id_large or DEFAULT_BEDROCK_MODEL
        self.client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self._usage = (0, 0)
        self._calls = 0

    @property
    def last_usage(self) -> tuple[int, int]:
        """Input and output tokens for the most recent call."""
        return self._usage

    @property
    def calls(self) -> int:
        """Number of model calls made."""
        return self._calls

    def propose(
        self, diagnosis: Diagnosis, source: str, previous_error: str | None = None
    ) -> RepairIntent:
        """Ask the model to select a repair pattern.

        Args:
            diagnosis: The proven diagnosis, serialized as the model's evidence.
            source: Source of the module holding the racing operations.
            previous_error: Validation error from the preceding attempt.

        Returns:
            The validated intent.

        Raises:
            ProviderError: The model returned something that is not a valid intent.

        """
        payload = {
            "diagnosis": diagnosis.model_dump(mode="json"),
            "source": source,
        }
        if previous_error:
            payload["validator_rejected_previous_intent"] = previous_error
        started = time.monotonic()
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": INTENT_SYSTEM}],
            messages=[{"role": "user", "content": [{"text": json.dumps(payload, indent=2)}]}],
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": _TOOL_NAME,
                            "description": "Return the repair intent for this race.",
                            "inputSchema": {"json": RepairIntent.model_json_schema()},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": _TOOL_NAME}},
            },
            inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
        )
        elapsed = time.monotonic() - started
        self._calls += 1
        usage = response.get("usage", {})
        tokens_in = int(usage.get("inputTokens", 0))
        tokens_out = int(usage.get("outputTokens", 0))
        self._usage = (tokens_in, tokens_out)
        log.info(
            "bedrock.call",
            attempt=self._calls,
            schema="RepairIntent",
            seconds=round(elapsed, 1),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=self.model_id.split("/")[-1],
        )
        return self._extract(response)

    def _extract(self, response: dict[str, Any]) -> RepairIntent:
        for block in response.get("output", {}).get("message", {}).get("content", []):
            tool_use = block.get("toolUse")
            if tool_use and tool_use.get("name") == _TOOL_NAME:
                try:
                    return RepairIntent.model_validate(tool_use["input"])
                except Exception as exc:
                    raise ProviderError(f"model returned an invalid intent: {exc}") from exc
        raise ProviderError("model response contained no repair intent")
