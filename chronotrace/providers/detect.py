"""Work out which model provider is actually usable on this machine.

The demo refuses to run on the reference policy, which is correct — a demo
driven by a hand-written policy shows this repository deciding for itself. But a
bare refusal is the worst thing a reviewer following the README can hit, so the
refusal has to come with the exact command that fixes it.

Detection is read-only and fast: it never installs anything, never pulls a
model, and never silently substitutes a different model than the one configured.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from chronotrace.config import Settings

__all__ = ["ProviderChoice", "detect"]

PROBE_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class ProviderChoice:
    """A usable provider, or an explanation of why there isn't one."""

    provider: str | None
    reason: str
    remedy: str = ""

    @property
    def usable(self) -> bool:
        """True when a real model provider was found."""
        return self.provider is not None


def ollama_models(host: str) -> list[str] | None:
    """Return the models an Ollama server has, or None when it is unreachable."""
    try:
        with urllib.request.urlopen(
            f"{host.rstrip('/')}/api/tags", timeout=PROBE_TIMEOUT_S
        ) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    return sorted(str(m.get("name", "")) for m in data.get("models", []))


def detect(settings: Settings) -> ProviderChoice:
    """Choose a usable provider, preferring one the operator already configured.

    Args:
        settings: Runtime settings.

    Returns:
        The chosen provider, or a choice carrying the command that would make
        one available.

    """
    if settings.provider == "bedrock":
        return ProviderChoice("bedrock", "configured explicitly")
    if settings.provider == "ollama":
        return ProviderChoice("ollama", f"configured explicitly ({settings.ollama_model})")
    if settings.provider == "fixture":
        return ProviderChoice("fixture", "replaying recorded calls")

    # Default is the reference policy, which the demo will not run on. Look for
    # something real before giving up.
    if settings.model_id_large:
        return ProviderChoice("bedrock", "a Bedrock model id is configured")

    models = ollama_models(settings.ollama_host)
    if models is None:
        return ProviderChoice(
            None,
            f"no model provider is configured, and no Ollama server is answering at "
            f"{settings.ollama_host}",
            remedy=(
                "Install Ollama from https://ollama.com, then:\n"
                f"    ollama pull {settings.ollama_model} && "
                f"CHRONOTRACE_PROVIDER=ollama uv run chronotrace repair --demo"
            ),
        )
    if settings.ollama_model in models:
        return ProviderChoice("ollama", f"found {settings.ollama_model} on the local Ollama server")
    available = ", ".join(models) if models else "none"
    return ProviderChoice(
        None,
        f"an Ollama server is running at {settings.ollama_host} but does not have "
        f"{settings.ollama_model} (it has: {available})",
        remedy=(
            f"    ollama pull {settings.ollama_model} && "
            "CHRONOTRACE_PROVIDER=ollama uv run chronotrace repair --demo"
        ),
    )
