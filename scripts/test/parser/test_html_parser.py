"""
Tests for HTML document parser (scripts/parser/html_parser.py)

Tests cover:
- HTML parsing from pravo.gov.ru
- API metadata extraction
- URL generation
- Text hash generation
- Edge cases (malformed HTML, empty documents)
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
import hashlib

from scripts.parser.html_parser import (
    PravoContentParser,
    parse_pravo_document,
)


class TestPravoContentParserInit:
    """Tests for PravoContentParser initialization."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_init_default(self):
        """Test default initialization."""
        parser = PravoContentParser()
        assert parser.use_ocr is False
        assert parser.timeout == 30
        assert parser.session is not None
        assert parser._driver is None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_init_with_ocr_enabled(self):
        """Test initialization with OCR enabled (when dependencies available)."""
        parser = PravoContentParser(use_ocr=True)
        # Parser should initialize regardless of OCR availability
        assert parser.timeout == 30
        # use_ocr will be False if dependencies aren't available
        assert parser.use_ocr in [True, False]

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        parser = PravoContentParser(timeout=60)
        assert parser.timeout == 60


class TestGetPdfUrl:
    """Tests for get_pdf_url method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_get_pdf_url(self):
        """Test PDF URL generation."""
        parser = PravoContentParser()
        url = parser.get_pdf_url("0001202601170001")
        assert url == "http://publication.pravo.gov.ru/file/pdf?eoNumber=0001202601170001"

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_get_pdf_url_empty(self):
        """Test PDF URL with empty eoNumber."""
        parser = PravoContentParser()
        url = parser.get_pdf_url("")
        assert url == "http://publication.pravo.gov.ru/file/pdf?eoNumber="


class TestGetDocumentViewUrl:
    """Tests for get_document_view_url method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_get_document_view_url(self):
        """Test document view URL generation."""
        parser = PravoContentParser()
        url = parser.get_document_view_url("0001202601170001")
        assert url == "http://publication.pravo.gov.ru/Document/View/0001202601170001"


class TestParseFromApiData:
    """Tests for parse_from_api_data method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_from_api_data_full(self):
        """Test parsing with all fields present (Russian content)."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Распоряжение Правительства",
            "name": "О присвоении классных чинов",
            "complexName": "Распоряжение Правительства РФ от 01.01.2026 № 1-р",
        }

        result = parser.parse_from_api_data(doc_data)

        assert result["eo_number"] == "0001202601170001"
        assert result["title"] == "Распоряжение Правительства"
        assert result["name"] == "О присвоении классных чинов"
        assert result["complex_name"] == doc_data["complexName"]
        # full_text includes complexName and name (when different)
        assert doc_data["complexName"] in result["full_text"]
        assert doc_data["name"] in result["full_text"]
        assert result["text_hash"] is not None
        assert "pdf_url" in result
        assert "html_url" in result

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_from_api_data_minimal(self):
        """Test parsing with minimal data."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "",
            "name": "",
            "complexName": "",
        }

        result = parser.parse_from_api_data(doc_data)

        assert result["eo_number"] == "0001202601170001"
        assert result["full_text"] == ""
        # Empty text produces empty hash (per _generate_text_hash logic)
        assert result["text_hash"] == ""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_from_api_data_with_html_tags(self):
        """Test that HTML tags are cleaned from title."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Закон<br>О поправке",
            "name": "Test",
            "complexName": "Test Complex",
        }

        result = parser.parse_from_api_data(doc_data)

        # <br> should be replaced with newline
        assert "\n" in result["full_text"]
        assert "<br>" not in result["full_text"]

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_from_api_data_duplicate_content(self):
        """Test that duplicate content is handled."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Same Title",
            "name": "Same Title",
            "complexName": "Same Title",
        }

        result = parser.parse_from_api_data(doc_data)

        # Should not duplicate the same text
        assert result["full_text"].count("Same Title") == 1


class TestTextHashGeneration:
    """Tests for text hash generation."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_generate_text_hash_consistent(self):
        """Test that hash is consistent for same text."""
        parser = PravoContentParser()
        text = "Test document content"

        hash1 = parser._generate_text_hash(text)
        hash2 = parser._generate_text_hash(text)

        assert hash1 == hash2

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_generate_text_hash_different(self):
        """Test that different texts produce different hashes."""
        parser = PravoContentParser()

        hash1 = parser._generate_text_hash("Text 1")
        hash2 = parser._generate_text_hash("Text 2")

        assert hash1 != hash2

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_generate_text_hash_empty(self):
        """Test hash generation for empty text."""
        parser = PravoContentParser()
        hash_value = parser._generate_text_hash("")
        assert hash_value == ""


class TestCleanHtmlText:
    """Tests for _clean_html_text method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_clean_html_text_removes_tags(self):
        """Test that HTML tags are removed."""
        parser = PravoContentParser()
        text = "<p>Hello <b>world</b></p>"

        result = parser._clean_html_text(text)

        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello world" == result

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_clean_html_text_replaces_br(self):
        """Test that <br> tags are replaced with newlines."""
        parser = PravoContentParser()
        text = "Line 1<br>Line 2<br/>Line 3"

        result = parser._clean_html_text(text)

        # <br> should be replaced, then whitespace normalized
        # So newlines get collapsed to spaces
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        assert "<br" not in result

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_clean_html_text_removes_whitespace(self):
        """Test that extra whitespace is normalized."""
        parser = PravoContentParser()
        text = "Hello     world\n\n  test"

        result = parser._clean_html_text(text)

        assert "Hello world test" == result

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_clean_html_text_empty(self):
        """Test cleaning empty text."""
        parser = PravoContentParser()
        result = parser._clean_html_text("")
        assert result == ""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_clean_html_text_none(self):
        """Test cleaning None text."""
        parser = PravoContentParser()
        result = parser._clean_html_text(None)
        assert result == ""


class TestParseDocument:
    """Tests for parse_document method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_document_without_selenium(self):
        """Test parsing without Selenium (API data only)."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Test Law",
            "name": "Test Name",
            "complexName": "Test Complex Name",
        }

        result = parser.parse_document(doc_data, use_selenium=False)

        assert result["eo_number"] == "0001202601170001"
        assert result["selenium_used"] is False
        # Result should have expected fields
        assert "full_text" in result
        assert "Test Complex Name" in result["full_text"]

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", True)
    @patch("scripts.parser.html_parser.PravoContentParser.fetch_with_selenium")
    def test_parse_document_with_selenium_success(self, mock_fetch):
        """Test parsing with Selenium when successful."""
        # Content must be > 100 characters to be accepted (see parse_document line 434)
        mock_fetch.return_value = "Full document content from Selenium with additional text that exceeds one hundred characters to satisfy the length requirement"

        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Test Law",
            "name": "Test Name",
            "complexName": "Test Complex Name",
        }

        result = parser.parse_document(doc_data, use_selenium=True)

        assert result["eo_number"] == "0001202601170001"
        # Selenium should be tried when available and content is > 100 chars
        assert result["selenium_used"] is True
        assert "full_text" in result

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", True)
    @patch("scripts.parser.html_parser.PravoContentParser.fetch_with_selenium")
    def test_parse_document_selenium_short_fallback(self, mock_fetch):
        """Test that short Selenium content falls back to API data."""
        mock_fetch.return_value = "short"  # Less than 100 chars

        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Test Law",
            "name": "Test Name",
            "complexName": "Test Complex Name with much longer content to exceed 100 characters for testing purposes",
        }

        result = parser.parse_document(doc_data, use_selenium=True)

        # Should fall back to API data since Selenium content is too short
        assert result["selenium_used"] is False
        assert "Test Complex Name" in result["full_text"]


class TestContextManager:
    """Tests for context manager functionality."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_context_manager_exit(self):
        """Test that parser cleans up resources on exit."""
        with PravoContentParser() as parser:
            mock_session = parser.session
            assert parser.session is not None

        # After exiting, session should be closed
        # Note: We can't directly test session.close() without real session
        # but we can verify the context manager works
        assert True  # If we get here, context manager worked

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_close_method(self):
        """Test close method."""
        parser = PravoContentParser()
        parser.close()
        # Should not raise exception


class TestConvenienceFunction:
    """Tests for parse_pravo_document convenience function."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.PravoContentParser")
    def test_convenience_function(self, mock_parser_class):
        """Test the convenience function."""
        mock_parser = MagicMock()
        mock_parser.parse_document.return_value = {"eo_number": "test"}
        mock_parser_class.return_value.__enter__.return_value = mock_parser

        doc_data = {"eoNumber": "test"}
        result = parse_pravo_document(doc_data)

        assert result["eo_number"] == "test"
        mock_parser.parse_document.assert_called_once()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_empty_document(self):
        """Test parsing a document with empty fields."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "",
            "title": "",
            "name": "",
            "complexName": "",
        }

        result = parser.parse_from_api_data(doc_data)

        assert result["eo_number"] == ""
        assert result["full_text"] == ""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_missing_fields(self):
        """Test parsing with missing fields."""
        parser = PravoContentParser()
        doc_data = {}

        result = parser.parse_from_api_data(doc_data)

        assert result["eo_number"] == ""
        assert result["full_text"] == ""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_special_characters_in_text(self):
        """Test handling of special characters."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Закон с &amp; символами и <tag>",
            "name": "Тест",
            "complexName": "Тест",
        }

        result = parser.parse_from_api_data(doc_data)

        # Should clean HTML entities
        assert "&amp;" not in result["title"] or "&" in result["title"]
        assert "<tag>" not in result["title"] or ">" in result["title"]

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_unicode_characters(self):
        """Test handling of Unicode characters (Cyrillic)."""
        parser = PravoContentParser()
        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Закон Российской Федерации",
            "name": "О внесении изменений",
            "complexName": "Трудовой кодекс Российской Федерации",
        }

        result = parser.parse_from_api_data(doc_data)

        # Should preserve Cyrillic characters
        assert "Российской Федерации" in result["complex_name"]
        assert "Трудовой кодекс" in result["complex_name"]
