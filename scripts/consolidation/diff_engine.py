"""
Backward compatibility shim for ArticleDiffEngine.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.consolidation.diff_engine.

Deprecated: Please import from country_modules.russia.consolidation.diff_engine instead.
"""
# Re-export everything from the new location
from country_modules.russia.consolidation.diff_engine import (
    ArticleDiffEngine,
    ArticleSnapshot,
    DiffResult,
    apply_amendment_to_article,
)

__all__ = [
    "ArticleDiffEngine",
    "ArticleSnapshot",
    "DiffResult",
    "apply_amendment_to_article",
]