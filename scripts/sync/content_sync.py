"""
Backward compatibility shim for ContentSyncService.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.sync.content_sync.

Deprecated: Please import from country_modules.russia.sync.content_sync instead.
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Re-export everything from the new location
from country_modules.russia.sync.content_sync import (
    ContentSyncService,
)

__all__ = [
    "ContentSyncService",
]