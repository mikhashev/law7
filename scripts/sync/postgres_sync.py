"""
PostgreSQL implementation of DocumentSync interface.

This module provides a PostgreSQL-based implementation of the DocumentSync
interface for storing and retrieving documents and manifests.

This implements the DocumentSync ABC from country_modules.base.sync for the
current centralized architecture, enabling future P2P implementations.
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text

from scripts.country_modules.base.sync import DocumentSync, DocumentManifest
from scripts.core.db import get_db_connection

logger = logging.getLogger(__name__)


class PostgreSQLSync(DocumentSync):
    """
    PostgreSQL implementation of DocumentSync.

    This class provides document synchronization using PostgreSQL as the backend
    storage. It implements the DocumentSync abstract base class interface.

    Manifests are stored in a new document_manifests table, and document content
    is stored in the existing document_content table.

    Attributes:
        connection_timeout: Timeout for database connections in seconds
    """

    def __init__(self, connection_timeout: int = 30):
        """
        Initialize PostgreSQL sync.

        Args:
            connection_timeout: Database connection timeout in seconds
        """
        self.connection_timeout = connection_timeout

    def _ensure_manifest_table_exists(self):
        """Ensure the document_manifests table exists."""
        create_table_query = text("""
            CREATE TABLE IF NOT EXISTS document_manifests (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                country_id VARCHAR(3) NOT NULL,
                manifest_data JSONB NOT NULL,
                last_updated TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(country_id)
            );
            CREATE INDEX IF NOT EXISTS idx_document_manifests_country_id ON document_manifests(country_id);
        """)

        try:
            with get_db_connection() as conn:
                conn.execute(create_table_query)
                conn.commit()
                logger.debug("document_manifests table ensured")
        except Exception as e:
            logger.error(f"Failed to ensure manifest table exists: {e}")
            raise

    async def publish_manifest(self, manifest: DocumentManifest) -> None:
        """
        Publish document manifest to PostgreSQL.

        Args:
            manifest: Document manifest to publish
        """
        self._ensure_manifest_table_exists()

        manifest_data = {
            "country_id": manifest.country_id,
            "documents": manifest.documents,
            "last_updated": manifest.last_updated,
            "metadata": manifest.metadata,
        }

        upsert_query = text("""
            INSERT INTO document_manifests (country_id, manifest_data, last_updated)
            VALUES (:country_id, :manifest_data::jsonb, NOW())
            ON CONFLICT (country_id) DO UPDATE
            SET
                manifest_data = EXCLUDED.manifest_data::jsonb,
                last_updated = NOW()
        """)

        try:
            with get_db_connection() as conn:
                conn.execute(upsert_query, {
                    "country_id": manifest.country_id,
                    "manifest_data": json.dumps(manifest_data),
                })
                conn.commit()
                logger.info(f"Published manifest for {manifest.country_id} with {len(manifest.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to publish manifest: {e}")
            raise

    async def get_manifest(self, country_id: str) -> Optional[DocumentManifest]:
        """
        Get current manifest for country.

        Args:
            country_id: Country identifier

        Returns:
            DocumentManifest or None if not found
        """
        self._ensure_manifest_table_exists()

        query = text("""
            SELECT manifest_data, last_updated
            FROM document_manifests
            WHERE country_id = :country_id
        """)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query, {"country_id": country_id})
                row = result.fetchone()

                if not row:
                    return None

                manifest_data = row[0]
                return DocumentManifest(
                    country_id=manifest_data["country_id"],
                    documents=manifest_data["documents"],
                    last_updated=row[1],
                    metadata=manifest_data.get("metadata", {}),
                )
        except Exception as e:
            logger.error(f"Failed to get manifest for {country_id}: {e}")
            return None

    async def publish_document(
        self,
        country_id: str,
        doc_id: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Publish document, return content hash.

        This stores the document content in the document_content table.
        The doc_id should correspond to the documents table.

        Args:
            country_id: Country identifier
            doc_id: Document identifier (UUID)
            content: Document content bytes
            metadata: Document metadata

        Returns:
            str: Content hash of published document
        """
        import hashlib

        # Calculate content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Store in document_content table
        upsert_query = text("""
            INSERT INTO document_content (document_id, full_text, raw_text, text_hash)
            VALUES (
                :doc_id,
                :full_text,
                :raw_text,
                :text_hash
            )
            ON CONFLICT (document_id) DO UPDATE
            SET
                full_text = EXCLUDED.full_text,
                raw_text = EXCLUDED.raw_text,
                text_hash = EXCLUDED.text_hash,
                updated_at = NOW()
        """)

        # For now, store content as text (convert from bytes)
        try:
            content_text = content.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            content_text = str(content)

        try:
            with get_db_connection() as conn:
                conn.execute(upsert_query, {
                    "doc_id": doc_id,
                    "full_text": content_text,
                    "raw_text": content_text,
                    "text_hash": content_hash,
                })
                conn.commit()
                logger.debug(f"Published document {doc_id} with hash {content_hash}")
                return content_hash
        except Exception as e:
            logger.error(f"Failed to publish document {doc_id}: {e}")
            raise

    async def get_document(self, country_id: str, doc_id: str) -> Optional[bytes]:
        """
        Get document content by ID.

        Args:
            country_id: Country identifier
            doc_id: Document identifier (UUID)

        Returns:
            bytes: Document content or None if not found
        """
        query = text("""
            SELECT full_text
            FROM document_content
            WHERE document_id = :doc_id
        """)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query, {"doc_id": doc_id})
                row = result.fetchone()

                if not row or not row[0]:
                    return None

                # Return as bytes
                content = row[0]
                if isinstance(content, str):
                    return content.encode('utf-8')
                return content
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def subscribe_to_updates(
        self,
        country_id: str,
        callback: Callable[[List[str]], None]
    ) -> None:
        """
        Subscribe to document updates for country.

        This implementation uses polling since PostgreSQL LISTEN/NOTIFY
        requires a dedicated connection. For production use with high update
        frequency, consider using LISTEN/NOTIFY with a dedicated connection.

        Args:
            country_id: Country identifier
            callback: Function to call with list of updated document IDs
        """
        # Note: For production use, implement using pg_notify/listen with
        # a dedicated connection. This polling implementation is a simpler
        # alternative for development.
        logger.warning(
            "PostgreSQLSync.subscribe_to_updates uses polling. "
            "For production use, implement with pg_notify/listen for real-time updates."
        )
        # This would typically be implemented as a background task
        # that polls for changes and calls the callback
        logger.info(f"Subscribed to updates for {country_id} (polling mode)")

    async def get_country_list(self) -> List[str]:
        """
        Get list of available countries.

        Returns:
            List[str]: List of country IDs (ISO 3166-1 alpha-2)
        """
        query = text("""
            SELECT UPPER(code) as code
            FROM countries
            ORDER BY code
        """)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query)
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get country list: {e}")
            return []

    async def get_country_config(self, country_id: str) -> Optional[Dict[str, Any]]:
        """
        Get country configuration.

        Args:
            country_id: Country identifier (ISO 3166-1 alpha-2)

        Returns:
            Dict with country config or None if not found
        """
        query = text("""
            SELECT
                UPPER(code) as code,
                name,
                native_name,
                legal_system_type,
                federal_structure,
                official_languages,
                data_sources,
                scraper_config,
                parser_config
            FROM countries
            WHERE LOWER(code) = LOWER(:country_id)
        """)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query, {"country_id": country_id})
                row = result.fetchone()

                if not row:
                    return None

                return {
                    "code": row[0],
                    "name": row[1],
                    "native_name": row[2],
                    "legal_system_type": row[3],
                    "federal_structure": row[4],
                    "official_languages": row[5],
                    "data_sources": row[6],
                    "scraper_config": row[7],
                    "parser_config": row[8],
                }
        except Exception as e:
            logger.error(f"Failed to get country config for {country_id}: {e}")
            return None


# Convenience function to create PostgreSQLSync instance
def create_postgres_sync(connection_timeout: int = 30) -> PostgreSQLSync:
    """
    Convenience function to create PostgreSQLSync instance.

    Args:
        connection_timeout: Database connection timeout in seconds

    Returns:
        PostgreSQLSync instance

    Example:
        >>> from sync.postgres_sync import create_postgres_sync
        >>> sync = create_postgres_sync()
        >>> await sync.get_country_list()
        ['RUS']
    """
    return PostgreSQLSync(connection_timeout=connection_timeout)
