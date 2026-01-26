"""
Base scraper abstract base class.

This module defines the interface that all country-specific scrapers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import date
from dataclasses import dataclass


@dataclass
class RawDocument:
    """Raw document from scraper."""

    doc_id: str
    url: str
    content: bytes
    content_type: str  # "text/html", "application/pdf"
    metadata: Dict[str, Any]


class BaseScraper(ABC):
    """
    Abstract base class for country-specific scrapers.

    All country scrapers must inherit from this class and implement
    the defined abstract methods.
    """

    @property
    @abstractmethod
    def country_id(self) -> str:
        """
        ISO 3166-1 alpha-3 code (e.g., 'RUS', 'DEU', 'USA').

        Returns:
            str: Three-letter country code
        """
        pass

    @property
    @abstractmethod
    def country_name(self) -> str:
        """
        Full country name (e.g., 'Russia', 'Germany').

        Returns:
            str: Full country name in English
        """
        pass

    @property
    @abstractmethod
    def country_code(self) -> str:
        """
        ISO 3166-1 alpha-2 code (e.g., 'RU', 'DE', 'US').

        Returns:
            str: Two-letter country code
        """
        pass

    @abstractmethod
    async def fetch_manifest(self, since: Optional[date] = None) -> Dict[str, Any]:
        """
        Get list of documents updated since date.

        Args:
            since: Only return documents updated after this date.
                   If None, return all documents.

        Returns:
            Dict with document list and metadata
        """
        pass

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> RawDocument:
        """
        Fetch single document by ID.

        Args:
            doc_id: Unique document identifier

        Returns:
            RawDocument with content and metadata
        """
        pass

    @abstractmethod
    async def fetch_updates(self, since: date) -> List[RawDocument]:
        """
        Fetch all documents updated since date.

        Args:
            since: Start date for updates

        Returns:
            List of RawDocument objects
        """
        pass

    @abstractmethod
    async def verify_document(self, doc_id: str, content_hash: str) -> bool:
        """
        Verify document content matches hash.

        Args:
            doc_id: Document identifier
            content_hash: Expected hash value

        Returns:
            bool: True if hash matches
        """
        pass
