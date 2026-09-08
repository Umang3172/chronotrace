"""Root conftest: put the repository on ``sys.path`` for the benchmark corpus."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config: pytest.Config) -> None:
    """When repeating tests on camera (--count > 1), keep terminal output clean and compact."""
    count = getattr(config.option, "count", 1)
    if count and count > 1:
        if config.option.tbstyle in ("auto", "long"):
            config.option.tbstyle = "no"
        config.option.reportchars = "N"

