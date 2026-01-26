"""
Base parser abstract base class.

This module defines the interface that all country-specific parsers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from .scraper import RawDocument


class BaseParser(ABC):
    """
    Abstract base class for country-specific parsers.

    All country parsers must inherit from this class and implement
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

    @abstractmethod
    async def parse_document(self, raw_doc: RawDocument) -> Dict[str, Any]:
        """
        Parse raw document, return structured data.

        Args:
            raw_doc: Raw document from scraper

        Returns:
            Dict with parsed document data including:
            - title: Document title
            - content: Extracted text content
            - metadata: Additional metadata (dates, references, etc.)
        """
        pass

    @abstractmethod
    async def extract_content(self, raw_doc: RawDocument) -> str:
        """
        Extract text content from document.

        Args:
            raw_doc: Raw document from scraper

        Returns:
            str: Extracted plain text content
        """
        pass

    @abstractmethod
    def parse_legal_references(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse legal document references (citations) from content.

        Args:
            content: Document text content

        Returns:
            List of reference dicts with cited documents/articles
        """
        pass
