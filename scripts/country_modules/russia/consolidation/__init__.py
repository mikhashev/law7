"""
Russia-specific consolidation engine.

This module contains the consolidation system for tracking historical
versions of Russian legal articles through amendments.

Components:
- Version Manager: Tracks article versions over time
- Amendment Parser: Extracts amendment operations
- Diff Engine: Applies amendments to create snapshots
- Consolidate: Orchestrates the consolidation process
"""
from .version_manager import VersionManager, VersionInfo, AmendmentChain, get_article_history
from .amendment_parser import AmendmentParser, ParsedAmendment, AmendmentTarget, AmendmentChange
from .diff_engine import ArticleDiffEngine, ArticleSnapshot, DiffResult
from .consolidate import CodeConsolidator, consolidate_code

__all__ = [
    # Version Manager
    "VersionManager",
    "VersionInfo",
    "AmendmentChain",
    "get_article_history",
    # Amendment Parser
    "AmendmentParser",
    "ParsedAmendment",
    "AmendmentTarget",
    "AmendmentChange",
    # Diff Engine
    "ArticleDiffEngine",
    "ArticleSnapshot",
    "DiffResult",
    # Consolidate
    "CodeConsolidator",
    "consolidate_code",
]
