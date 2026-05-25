"""
Add the slack-notifier service directory to sys.path so tests can import
modules that use flat (non-package) imports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
