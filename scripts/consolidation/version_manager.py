"""
Backward compatibility shim for VersionManager.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.consolidation.version_manager.

Deprecated: Please import from country_modules.russia.consolidation.version_manager instead.
"""
# Re-export everything from the new location
from country_modules.russia.consolidation.version_manager import (
    VersionManager,
    VersionInfo,
    AmendmentChain,
    get_article_history,
)

__all__ = [
    "VersionManager",
    "VersionInfo",
    "AmendmentChain",
    "get_article_history",
]