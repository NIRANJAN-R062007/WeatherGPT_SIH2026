"""pytest sys.path shim.

main.py and friends use flat imports (`from i18n import render`) and only
resolve when run from inside `prototype/ask_service/`. This lets pytest work
from the repo root too.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
