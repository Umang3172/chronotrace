"""Execution fingerprints (E2).

Two traces are comparable only if they were produced by the same code in the
same environment. "Same commit" is necessary but not sufficient: a different
Python patch release or a different dependency lock is an environmental
explanation for divergence, and a judge is entitled to ask how that was ruled
out. Comparing traces across fingerprints is refused, not warned about.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from pathlib import Path

from chronotrace.contracts import ExecutionFingerprint

_ENV_KEYS = ("PYTHONHASHSEED", "CHRONOTRACE_SEED", "CI", "TZ")


def _git_sha(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _lock_hash(root: Path) -> str:
    for candidate in ("uv.lock", "requirements.txt", "pyproject.toml"):
        path = root / candidate
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return "none"


def _env_hash() -> str:
    material = "|".join(f"{key}={os.environ.get(key, '')}" for key in _ENV_KEYS)
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def compute(test_id: str, root: Path | None = None) -> ExecutionFingerprint:
    """Build the fingerprint for a run of ``test_id``."""
    root = root or Path.cwd()
    return ExecutionFingerprint(
        commit_sha=_git_sha(root),
        python_version=platform.python_version(),
        dependency_lock_hash=_lock_hash(root),
        container_image=os.environ.get("CHRONOTRACE_IMAGE", "process"),
        test_id=test_id,
        env_hash=_env_hash(),
    )


def comparable(left: ExecutionFingerprint, right: ExecutionFingerprint) -> bool:
    """Return True when two traces may be diffed against one another."""
    return left.model_dump() == right.model_dump()
