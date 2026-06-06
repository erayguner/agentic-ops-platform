"""Add the agents/ directory to sys.path so tests can import the aop_common package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
