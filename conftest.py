"""Root conftest: put the repository on ``sys.path`` for the benchmark corpus."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
