"""
Backward compatibility shim for CodeConsolidator.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.consolidation.consolidate.

Deprecated: Please import from country_modules.russia.consolidation.consolidate instead.
"""
# Re-export everything from the new location
from country_modules.russia.consolidation.consolidate import (
    CodeConsolidator,
    consolidate_code,
    CODE_METADATA,
    main,
)

__all__ = [
    "CodeConsolidator",
    "consolidate_code",
    "CODE_METADATA",
    "main",
]