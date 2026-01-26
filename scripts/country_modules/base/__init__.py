"""
Base classes for country modules.

This module defines abstract base classes (ABCs) that all country-specific
implementations must follow.
"""

from .scraper import BaseScraper, RawDocument
from .parser import BaseParser
from .sync import DocumentSync, DocumentManifest

__all__ = [
    "BaseScraper",
    "RawDocument",
    "BaseParser",
    "DocumentSync",
    "DocumentManifest",
]
