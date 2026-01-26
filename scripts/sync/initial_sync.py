"""
Backward compatibility shim for InitialSyncService.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.sync.initial_sync.

Deprecated: Please import from country_modules.russia.sync.initial_sync instead.
"""
# Re-export everything from the new location
from country_modules.russia.sync.initial_sync import (
    InitialSyncService,
    run_daily_sync,
)

__all__ = [
    "InitialSyncService",
    "run_daily_sync",
]