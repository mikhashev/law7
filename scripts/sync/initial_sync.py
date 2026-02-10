"""
Backward compatibility shim for InitialSyncService.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.sync.initial_sync.

Deprecated: Please import from country_modules.russia.sync.initial_sync instead.
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Re-export everything from the new location
from country_modules.russia.sync.initial_sync import (
    InitialSyncService,
    run_daily_sync,
    main as _main,
)

__all__ = [
    "InitialSyncService",
    "run_daily_sync",
    "main",
]

# Entry point for backward compatibility
if __name__ == "__main__":
    _main()