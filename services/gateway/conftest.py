"""pytest sys.path shim — lets `import main` resolve when pytest runs from the
repo root (same trick as services/orchestrator/conftest.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
