"""
Document sync abstract base class.

This module defines the interface for document synchronization mechanisms.
The DocumentSync interface allows different sync implementations (PostgreSQL,
IPFS, D-PC, etc.) to be used interchangeably.
"""

from abc import ABC, abstractmethod
from typing import List, Callable, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DocumentManifest:
    """
    List of documents + their versions.

    This manifest represents the current state of documents for a country,
    including content hashes for verification.
    """
    country_id: str
    documents: Dict[str, str] = field(default_factory=dict)  # doc_id -> content_hash
    last_updated: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_document(self, doc_id: str, content_hash: str) -> None:
        """Add or update a document in the manifest."""
        self.documents[doc_id] = content_hash

    def get_document_hash(self, doc_id: str) -> Optional[str]:
        """Get content hash for a document."""
        return self.documents.get(doc_id)


class DocumentSync(ABC):
    """
    Abstract interface for document synchronization.

    This interface will be implemented by:
    1. PostgreSQLSync (current implementation, local-only) - Phase 7
    2. IPFSSync (IPFS-based P2P, Phase 0 PoC)
    3. DPCSync (D-PC Messenger-based, Phase 0 PoC)

    The sync layer abstracts how documents are stored and retrieved,
    allowing the system to work with different backends.
    """

    @abstractmethod
    async def publish_manifest(self, manifest: DocumentManifest) -> None:
        """
        Publish document manifest to network.

        Args:
            manifest: Document manifest to publish
        """
        pass

    @abstractmethod
    async def get_manifest(self, country_id: str) -> Optional[DocumentManifest]:
        """
        Get current manifest for country.

        Args:
            country_id: Country identifier

        Returns:
            DocumentManifest or None if not found
        """
        pass

    @abstractmethod
    async def publish_document(
        self,
        country_id: str,
        doc_id: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Publish document, return content hash.

        Args:
            country_id: Country identifier
            doc_id: Document identifier
            content: Document content bytes
            metadata: Document metadata

        Returns:
            str: Content hash of published document
        """
        pass

    @abstractmethod
    async def get_document(self, country_id: str, doc_id: str) -> Optional[bytes]:
        """
        Get document content by ID.

        Args:
            country_id: Country identifier
            doc_id: Document identifier

        Returns:
            bytes: Document content or None if not found
        """
        pass

    @abstractmethod
    async def subscribe_to_updates(
        self,
        country_id: str,
        callback: Callable[[List[str]], None]
    ) -> None:
        """
        Subscribe to document updates for country.

        Args:
            country_id: Country identifier
            callback: Function to call with list of updated document IDs
        """
        pass

    @abstractmethod
    async def get_country_list(self) -> List[str]:
        """
        Get list of available countries.

        Returns:
            List[str]: List of country IDs
        """
        pass

    @abstractmethod
    async def get_country_config(self, country_id: str) -> Optional[Dict[str, Any]]:
        """
        Get country configuration.

        Args:
            country_id: Country identifier

        Returns:
            Dict with country config or None if not found
        """
        pass
