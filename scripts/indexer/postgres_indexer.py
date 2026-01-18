"""
PostgreSQL batch upsert indexer.
Based on yandex-games-bi-suite batch saver pattern.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Table, MetaData, insert, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.db import get_db_connection
from core.config import SYNC_BATCH_SIZE

logger = logging.getLogger(__name__)


class PostgresIndexer:
    """
    Batch upsert indexer for PostgreSQL.
    Handles bulk insert/update operations with conflict resolution.
    """

    def __init__(self, batch_size: int = SYNC_BATCH_SIZE):
        """
        Initialize the indexer.

        Args:
            batch_size: Number of records per batch
        """
        self.batch_size = batch_size
        self.metadata = MetaData()

        # Define tables
        self._define_tables()

    def _define_tables(self):
        """Define SQLAlchemy table metadata."""
        self.documents_table = Table(
            "documents",
            self.metadata,
            autoload_with=lambda: get_db_connection(),
        )

        self.document_content_table = Table(
            "document_content",
            self.metadata,
            autoload_with=lambda: get_db_connection(),
        )

        self.signatory_authorities_table = Table(
            "signatory_authorities",
            self.metadata,
            autoload_with=lambda: get_db_connection(),
        )

        self.document_types_table = Table(
            "document_types",
            self.metadata,
            autoload_with=lambda: get_db_connection(),
        )

        self.publication_blocks_table = Table(
            "publication_blocks",
            self.metadata,
            autoload_with=lambda: get_db_connection(),
        )

    def batch_upsert_documents(
        self,
        documents: List[Dict[str, Any]],
        country_id: int = 1,  # Russia
    ) -> int:
        """
        Batch upsert documents to the database.

        Uses INSERT ... ON CONFLICT DO UPDATE for efficient upserts.

        Args:
            documents: List of document dictionaries from API
            country_id: Country ID (default: 1 for Russia)

        Returns:
            Number of documents upserted

        Example:
            >>> indexer = PostgresIndexer()
            >>> docs = [{"eoNumber": "0001202601170001", ...}]
            >>> count = indexer.batch_upsert_documents(docs)
        """
        if not documents:
            return 0

        logger.info(f"Upserting {len(documents)} documents in batches of {self.batch_size}")

        total_upserted = 0

        # Process in batches
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i : i + self.batch_size]

            # Transform API response to database schema
            records = []
            for doc in batch:
                records.append(self._transform_document(doc, country_id))

            try:
                with get_db_connection() as conn:
                    trans = conn.begin()

                    try:
                        # Create INSERT statement with ON CONFLICT DO UPDATE
                        stmt = pg_insert(self.documents_table).values(records)

                        # Define update columns (all except key columns)
                        update_columns = {
                            col.name: stmt.excluded[col.name]
                            for col in self.documents_table.columns
                            if col.name not in ["id", "eo_number"]
                        }

                        stmt = stmt.on_conflict_do_update(
                            index_elements=["eo_number"],
                            set_=update_columns,
                        )

                        conn.execute(stmt)
                        trans.commit()

                        total_upserted += len(batch)
                        logger.debug(f"  Batch {i // self.batch_size + 1}: {len(batch)} documents")

                    except Exception as e:
                        trans.rollback()
                        logger.error(f"Error upserting batch: {e}")
                        raise

            except Exception as e:
                logger.error(f"Failed to upsert batch starting at index {i}: {e}")
                raise

        logger.info(f"Total documents upserted: {total_upserted}")
        return total_upserted

    def _transform_document(
        self, api_doc: Dict[str, Any], country_id: int
    ) -> Dict[str, Any]:
        """
        Transform API document response to database schema.

        Args:
            api_doc: Document from API response
            country_id: Country ID

        Returns:
            Dictionary matching database schema
        """
        return {
            "eo_number": api_doc.get("eoNumber"),
            "title": api_doc.get("title"),
            "name": api_doc.get("name"),
            "complex_name": api_doc.get("complexName"),
            "document_number": api_doc.get("number"),
            "document_date": self._parse_date(api_doc.get("documentDate")),
            "publish_date": self._parse_date(api_doc.get("publishDateShort")),
            "view_date": api_doc.get("viewDate"),
            "pages_count": api_doc.get("pagesCount"),
            "pdf_file_size": api_doc.get("pdfFileLength"),
            "has_svg": api_doc.get("hasSvg", False),
            "zip_file_length": api_doc.get("zipFileLength"),
            "jd_reg_number": api_doc.get("jdRegNumber"),
            "jd_reg_date": self._parse_date(api_doc.get("jdRegDate")),
            "signatory_authority_id": api_doc.get("signatoryAuthorityId"),
            "document_type_id": api_doc.get("documentTypeId"),
            "country_id": country_id,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string from API response.

        Args:
            date_str: Date string in various formats

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        try:
            # Try ISO format first (2026-01-17T00:00:00)
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("T", " ").split(".")[0])
            # Try simple format (2026-01-17)
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse date: {date_str}")
            return None

    def batch_upsert_signatory_authorities(
        self, authorities: List[Dict[str, Any]]
    ) -> int:
        """
        Batch upsert signatory authorities.

        Args:
            authorities: List of authority dictionaries

        Returns:
            Number of authorities upserted
        """
        if not authorities:
            return 0

        logger.info(f"Upserting {len(authorities)} signatory authorities")

        records = []
        for auth in authorities:
            records.append(
                {
                    "id": auth.get("id"),
                    "name": auth.get("name"),
                    "code": auth.get("code"),
                    "description": auth.get("description"),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )

        with get_db_connection() as conn:
            trans = conn.begin()

            try:
                stmt = pg_insert(self.signatory_authorities_table).values(records)

                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "name": stmt.excluded.name,
                        "code": stmt.excluded.code,
                        "description": stmt.excluded.description,
                        "updated_at": datetime.now(),
                    },
                )

                conn.execute(stmt)
                trans.commit()

                logger.info(f"Upserted {len(records)} signatory authorities")
                return len(records)

            except Exception as e:
                trans.rollback()
                logger.error(f"Error upserting signatory authorities: {e}")
                raise

    def batch_upsert_document_types(
        self, doc_types: List[Dict[str, Any]]
    ) -> int:
        """
        Batch upsert document types.

        Args:
            doc_types: List of document type dictionaries

        Returns:
            Number of document types upserted
        """
        if not doc_types:
            return 0

        logger.info(f"Upserting {len(doc_types)} document types")

        records = []
        for dt in doc_types:
            records.append(
                {
                    "id": dt.get("id"),
                    "name": dt.get("name"),
                    "code": dt.get("code"),
                    "description": dt.get("description"),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )

        with get_db_connection() as conn:
            trans = conn.begin()

            try:
                stmt = pg_insert(self.document_types_table).values(records)

                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "name": stmt.excluded.name,
                        "code": stmt.excluded.code,
                        "description": stmt.excluded.description,
                        "updated_at": datetime.now(),
                    },
                )

                conn.execute(stmt)
                trans.commit()

                logger.info(f"Upserted {len(records)} document types")
                return len(records)

            except Exception as e:
                trans.rollback()
                logger.error(f"Error upserting document types: {e}")
                raise

    def upsert_document_content(
        self,
        document_id: str,
        full_text: Optional[str] = None,
        raw_text: Optional[str] = None,
        pdf_url: Optional[str] = None,
        html_url: Optional[str] = None,
        text_hash: Optional[str] = None,
    ) -> bool:
        """
        Upsert document content for a specific document.

        Args:
            document_id: Document UUID
            full_text: Cleaned full text
            raw_text: Original extracted text
            pdf_url: URL to PDF file
            html_url: URL to HTML version
            text_hash: Hash for change detection

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Upserting content for document {document_id}")

        record = {
            "document_id": document_id,
            "full_text": full_text,
            "raw_text": raw_text,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "text_hash": text_hash,
            "updated_at": datetime.now(),
        }

        try:
            with get_db_connection() as conn:
                trans = conn.begin()

                try:
                    stmt = pg_insert(self.document_content_table).values(record)

                    stmt = stmt.on_conflict_do_update(
                        index_elements=["document_id"],
                        set_={
                            "full_text": stmt.excluded.full_text,
                            "raw_text": stmt.excluded.raw_text,
                            "pdf_url": stmt.excluded.pdf_url,
                            "html_url": stmt.excluded.html_url,
                            "text_hash": stmt.excluded.text_hash,
                            "updated_at": datetime.now(),
                        },
                    )

                    conn.execute(stmt)
                    trans.commit()
                    return True

                except Exception as e:
                    trans.rollback()
                    logger.error(f"Error upserting document content: {e}")
                    return False

        except Exception as e:
            logger.error(f"Failed to upsert document content: {e}")
            return False

    def get_document_count(self) -> int:
        """
        Get total number of documents in database.

        Returns:
            Document count
        """
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM documents"))
            return result.scalar()

    def get_last_document_date(self) -> Optional[datetime]:
        """
        Get the date of the most recent document.

        Returns:
            Most recent document date or None
        """
        with get_db_connection() as conn:
            result = conn.execute(
                text("SELECT MAX(publish_date) FROM documents WHERE publish_date IS NOT NULL")
            )
            return result.scalar()
