"""
pytest configuration for database tests.
Sets up Python path to resolve module imports.
"""

import sys
from pathlib import Path

# Add the scripts directory to Python path
# This allows imports like 'from core.db import ...' to work
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))
