"""
Tests for PostgreSQL batch indexer (scripts/indexer/postgres_indexer.py)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime
from sqlalchemy import Table, MetaData, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from scripts.indexer.postgres_indexer import PostgresIndexer


class TestPostgresIndexerInit:
    """Tests for PostgresIndexer initialization."""

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_init_with_default_batch_size(self, mock_engine):
        """Test initialization with default batch size."""
        indexer = PostgresIndexer()

        # SYNC_BATCH_SIZE defaults to 30
        assert indexer.batch_size == 30
        assert isinstance(indexer.metadata, MetaData)

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_init_with_custom_batch_size(self, mock_engine):
        """Test initialization with custom batch size."""
        indexer = PostgresIndexer(batch_size=50)

        assert indexer.batch_size == 50


class TestTransformDocument:
    """Tests for _transform_document method."""

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_transform_document_basic_fields(self, mock_engine):
        """Test basic document transformation."""
        indexer = PostgresIndexer()

        api_doc = {
            "eoNumber": "0001202601170001",
            "title": "Test Title",
            "name": "Test Name",
            "documentDate": "2026-01-17",
        }

        result = indexer._transform_document(api_doc, country_id=1)

        assert result["eo_number"] == "0001202601170001"
        assert result["title"] == "Test Title"
        assert result["name"] == "Test Name"
        assert result["country_id"] == 1
        assert isinstance(result["document_date"], datetime)
        assert isinstance(result["created_at"], datetime)

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_transform_document_all_fields(self, mock_engine):
        """Test transformation with all fields present."""
        indexer = PostgresIndexer()

        api_doc = {
            "eoNumber": "0001202601170001",
            "title": "Title",
            "name": "Name",
            "complexName": "Complex Name",
            "number": "123",
            "documentDate": "2026-01-17T00:00:00",
            "publishDateShort": "2026-01-18",
            "viewDate": "2026-01-19T00:00:00",
            "pagesCount": 10,
            "pdfFileLength": 12345,
            "hasSvg": True,
            "zipFileLength": 54321,
            "jdRegNumber": "JD123",
            "jdRegDate": "2026-01-20",
            "signatoryAuthorityId": "auth-123",
            "documentTypeId": "type-456",
        }

        result = indexer._transform_document(api_doc, country_id=1)

        assert result["eo_number"] == "0001202601170001"
        assert result["complex_name"] == "Complex Name"
        assert result["document_number"] == "123"
        assert result["pages_count"] == 10
        assert result["pdf_file_size"] == 12345
        assert result["has_svg"] is True
        assert result["zip_file_length"] == 54321
        assert result["jd_reg_number"] == "JD123"
        assert result["signatory_authority_id"] == "auth-123"
        assert result["document_type_id"] == "type-456"

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_transform_document_missing_optional_fields(self, mock_engine):
        """Test transformation with missing optional fields."""
        indexer = PostgresIndexer()

        api_doc = {
            "eoNumber": "0001202601170001",
        }

        result = indexer._transform_document(api_doc, country_id=1)

        assert result["eo_number"] == "0001202601170001"
        assert result["title"] is None
        assert result["name"] is None
        assert result["document_date"] is None
        assert result["pages_count"] is None

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_transform_document_with_publication_block_id(self, mock_engine):
        """Test transformation with publication_block_id."""
        indexer = PostgresIndexer()

        api_doc = {
            "eoNumber": "0001202601170001",
            "title": "Test",
        }

        block_id = "uuid-123-456"
        result = indexer._transform_document(api_doc, country_id=1, publication_block_id=block_id)

        assert result["publication_block_id"] == block_id


class TestParseDate:
    """Tests for _parse_date method."""

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_parse_date_iso_format(self, mock_engine):
        """Test parsing ISO format date with time."""
        indexer = PostgresIndexer()

        result = indexer._parse_date("2026-01-17T00:00:00")

        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 17

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_parse_date_simple_format(self, mock_engine):
        """Test parsing simple date format."""
        indexer = PostgresIndexer()

        result = indexer._parse_date("2026-01-17")

        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 17

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_parse_date_with_microseconds(self, mock_engine):
        """Test parsing date with microseconds."""
        indexer = PostgresIndexer()

        result = indexer._parse_date("2026-01-17T00:00:00.123456")

        assert isinstance(result, datetime)
        assert result.year == 2026

    @patch("scripts.indexer.postgres_indexer.engine")
    @patch("scripts.indexer.postgres_indexer.logger")
    def test_parse_date_invalid_format(self, mock_logger, mock_engine):
        """Test parsing invalid date string."""
        indexer = PostgresIndexer()

        result = indexer._parse_date("invalid-date")

        assert result is None
        mock_logger.warning.assert_called_once()

    @patch("scripts.indexer.postgres_indexer.engine")
    def test_parse_date_none(self, mock_engine):
        """Test parsing None value."""
        indexer = PostgresIndexer()

        result = indexer._parse_date(None)

        assert result is None


class TestGetPublicationBlockId:
    """Tests for _get_publication_block_id method."""

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    def test_get_publication_block_id_found(self, mock_engine, mock_get_conn):
        """Test finding publication block by code."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("uuid-123-456",)
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        block_id = indexer._get_publication_block_id("president")

        assert block_id == "uuid-123-456"
        mock_conn.execute.assert_called_once()

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    @patch("scripts.indexer.postgres_indexer.logger")
    def test_get_publication_block_id_not_found(self, mock_logger, mock_engine, mock_get_conn):
        """Test when publication block not found."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        block_id = indexer._get_publication_block_id("nonexistent")

        assert block_id is None
        mock_logger.warning.assert_called_once()

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    @patch("scripts.indexer.postgres_indexer.logger")
    def test_get_publication_block_id_error(self, mock_logger, mock_engine, mock_get_conn):
        """Test error handling in get_publication_block_id."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("DB error")
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        block_id = indexer._get_publication_block_id("president")

        assert block_id is None
        mock_logger.error.assert_called_once()


class TestGetDocumentCount:
    """Tests for get_document_count method."""

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    def test_get_document_count(self, mock_engine, mock_get_conn):
        """Test getting document count."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 12345
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        count = indexer.get_document_count()

        assert count == 12345
        mock_conn.execute.assert_called_once()

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    def test_get_document_count_empty(self, mock_engine, mock_get_conn):
        """Test getting document count when empty."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        count = indexer.get_document_count()

        assert count == 0


class TestGetLastDocumentDate:
    """Tests for get_last_document_date method."""

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    def test_get_last_document_date(self, mock_engine, mock_get_conn):
        """Test getting most recent document date."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_date = datetime(2026, 1, 17, 12, 0, 0)
        mock_result.scalar.return_value = mock_date
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        date = indexer.get_last_document_date()

        assert date == mock_date
        mock_conn.execute.assert_called_once()

    @patch("scripts.indexer.postgres_indexer.get_db_connection")
    @patch("scripts.indexer.postgres_indexer.engine")
    def test_get_last_document_date_none(self, mock_engine, mock_get_conn):
        """Test getting last document date when no documents."""
        indexer = PostgresIndexer()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        date = indexer.get_last_document_date()

        assert date is None


# Note: Tests for batch_upsert_documents, batch_upsert_signatory_authorities,
# batch_upsert_document_types, and upsert_document_content are skipped because
# they require SQLAlchemy table autoload which is complex to mock properly.
# These methods are integration-level tests that would be better tested with:
# 1. An actual test database (integration tests)
# 2. More sophisticated mocking of SQLAlchemy internals
# 3. Or by refactoring the code to separate table definition from business logic
#
# The current tests provide good coverage of:
# - Document transformation logic (_transform_document)
# - Date parsing (_parse_date)
# - Publication block ID lookup (_get_publication_block_id)
# - Simple query methods (get_document_count, get_last_document_date)
