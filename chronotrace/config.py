"""Central configuration (§33).

Config lives here and nowhere else: scattered ``os.getenv`` calls are how a
system ends up with two different timeouts for the same thing. Provider
selection is one environment variable, so the local build and the Bedrock build
are the same code path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from the environment with a ``CHRONOTRACE_`` prefix."""

    model_config = SettingsConfigDict(env_prefix="CHRONOTRACE_", env_file=".env", extra="ignore")

    provider: Literal["reference-policy", "bedrock", "ollama", "fixture"] = "reference-policy"
    """``reference-policy`` is a hand-written test double, not a model."""
    telemetry: Literal["jsonl", "cloudwatch"] = "jsonl"
    registry: Literal["sqlite", "dynamodb"] = "sqlite"
    isolation: Literal["process", "docker"] = "process"

    aws_region: str = "ap-south-1"
    model_id_small: str = ""
    model_id_large: str = ""

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    model_temperature: float = 0.0
    model_seed: int = 1729
    model_max_tokens: int = 4096
    model_timeout_s: float = 600.0
    max_attempts: int = 3
    """Attempts allowed per case to produce usable model output. Binds every arm."""

    workdir: Path = Path(".chronotrace")
    fixtures_dir: Path = Path("fixtures")
    telemetry_dir: Path = Path("telemetry")

    run_timeout_s: float = 30.0
    """Wall-clock cap on any verification subprocess. A breach is a deadlock (INV-4)."""
    gate_timeout_s: float = 5.0
    """Cap on a single forced-ordering gate. A breach means INFEASIBLE, not FAIL."""
    max_rounds: int = 5
    """INV-8."""
    statistical_runs: int = 20
    """Tier 3 sample size for the demo path. Full runs are an offline concern (V-5)."""
    pct_runs: int = 0
    """Tier 2 sample size. Zero disables PCT, which is then reported as not attempted."""
    allow_production_repair: bool = False
    """INV-7 / S2. Off by default; production-scope races abstain."""

    def ensure_dirs(self) -> None:
        """Create the working directories this run will write to."""
        for path in (self.workdir, self.fixtures_dir, self.telemetry_dir):
            path.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(settings: Settings) -> None:
    """Replace the settings singleton. Used by the CLI and by tests."""
    global _settings
    _settings = settings
