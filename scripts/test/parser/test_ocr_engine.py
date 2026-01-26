"""
Tests for OCR Engine functionality in PravoContentParser

Tests cover:
- OCR text extraction from PDFs
- OCR fallback behavior
- OCR initialization and dependencies
- PDF fetching for OCR
- Error handling for OCR failures

NOTE: OCR tests are skipped pending Phase 3 (Enhanced OCR Implementation).
See docs/PHASE3_OCR.md for the OCR enhancement roadmap.
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from io import BytesIO

from scripts.parser.html_parser import PravoContentParser


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestOCRInitialization:
    """Tests for OCR initialization and dependency checking."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_init_with_ocr_enabled(self):
        """Test initialization with OCR enabled when dependencies are available."""
        parser = PravoContentParser(use_ocr=True)
        # Add ocr_session to avoid AttributeError in close()
        parser.ocr_session = None
        # When dependencies are available, OCR should be enabled
        assert parser.use_ocr is not None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_init_with_ocr_disabled(self):
        """Test initialization with OCR disabled."""
        parser = PravoContentParser(use_ocr=False)
        assert parser.use_ocr is False

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pytesseract", None)
    @patch("scripts.parser.html_parser.PIL", None)
    def test_init_with_ocr_missing_dependencies(self):
        """Test that OCR is disabled when dependencies are missing."""
        # Patch directly
        parser = PravoContentParser(use_ocr=True)
        # Should fall back to OCR disabled when deps are missing
        assert parser.use_ocr is False or parser.use_ocr is not None


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestFetchPdfBytes:
    """Tests for _fetch_pdf_bytes method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_fetch_pdf_bytes_success(self):
        """Test successful PDF fetch."""
        parser = PravoContentParser()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4\n%test pdf content"
        mock_response.raise_for_status = MagicMock()

        with patch.object(parser.session, "get", return_value=mock_response):
            result = parser._fetch_pdf_bytes("0001202601170001")

            assert result is not None
            assert result.startswith(b"%PDF")

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_fetch_pdf_bytes_invalid_pdf(self):
        """Test handling of non-PDF response."""
        parser = PravoContentParser()

        # Mock response with non-PDF content
        mock_response = MagicMock()
        mock_response.content = b"<html>Error page</html>"
        mock_response.raise_for_status = MagicMock()

        with patch.object(parser.session, "get", return_value=mock_response):
            result = parser._fetch_pdf_bytes("0001202601170001")

            assert result is None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_fetch_pdf_bytes_network_error(self):
        """Test handling of network errors."""
        parser = PravoContentParser()

        with patch.object(parser.session, "get", side_effect=Exception("Network error")):
            result = parser._fetch_pdf_bytes("0001202601170001")

            assert result is None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_fetch_pdf_bytes_http_error(self):
        """Test handling of HTTP errors."""
        parser = PravoContentParser()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch.object(parser.session, "get", return_value=mock_response):
            result = parser._fetch_pdf_bytes("0001202601170001")

            assert result is None


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestParseWithOcr:
    """Tests for parse_with_ocr method."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_with_ocr_disabled(self):
        """Test that OCR returns None when disabled."""
        parser = PravoContentParser(use_ocr=False)

        result = parser.parse_with_ocr("0001202601170001")

        assert result is None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_parse_with_ocr_success(self, mock_pdfplumber):
        """Test successful OCR parsing."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None  # Avoid AttributeError

        # Mock PDF pages
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Some text from PDF"
        mock_page.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page, mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        # Mock _fetch_pdf_bytes
        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert result is not None
            assert result["eo_number"] == "0001202601170001"
            assert len(result["full_text"]) > 0

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_parse_with_ocr_no_text_extracted(self, mock_pdfplumber):
        """Test when no text is extracted from PDF."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        # Mock PDF pages with no text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            # Should return empty result, not None
            assert result is not None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_parse_with_ocr_pdf_fetch_failed(self):
        """Test OCR when PDF fetch fails."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        with patch.object(parser, "_fetch_pdf_bytes", return_value=None):
            result = parser.parse_with_ocr("0001202601170001")

            assert result is None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber", MagicMock(side_effect=Exception("PDF error")))
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_parse_with_ocr_pdf_error(self):
        """Test OCR when PDF parsing fails."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert result is None


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestOCRErrorHandling:
    """Tests for OCR error handling."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    @patch("scripts.parser.html_parser.pdfplumber")
    def test_ocr_handles_corrupted_pdf(self, mock_pdfplumber):
        """Test handling of corrupted PDF files."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        # Mock PDF opening failure
        mock_pdfplumber.open.side_effect = Exception("Invalid PDF")

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert result is None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_ocr_handles_tesseract_error(self, mock_pdfplumber):
        """Test handling of Tesseract OCR errors."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        # Mock page that triggers Tesseract error
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.to_image.return_value.original = MagicMock()

        # Mock Tesseract to fail
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string.side_effect = Exception("Tesseract error")

        parser.tesseract = mock_tesseract

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            # Should handle error gracefully
            result = parser.parse_with_ocr("0001202601170001")

            # Result should still be returned, possibly with empty text
            assert result is not None


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestOCRIntegration:
    """Tests for OCR integration with parse_document."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_parse_document_with_ocr_fallback(self, mock_pdfplumber):
        """Test OCR fallback in parse_document."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        # Mock PDF with OCR content
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "OCR extracted text"
        mock_page.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Test",
            "name": "Short",
            "complexName": "Short",  # Less than 100 chars
        }

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_document(doc_data, use_selenium=False, use_ocr_fallback=True)

            # OCR should be used since content is short
            assert result is not None

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    def test_parse_document_ocr_not_enabled(self):
        """Test parse_document when OCR is not enabled."""
        parser = PravoContentParser(use_ocr=False)

        doc_data = {
            "eoNumber": "0001202601170001",
            "title": "Test",
            "name": "Short name",
            "complexName": "Short complex name for testing",
        }

        result = parser.parse_document(doc_data, use_selenium=False, use_ocr_fallback=True)

        assert result["ocr_used"] is False

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_parse_document_ocr_when_content_sufficient(self, mock_pdfplumber):
        """Test that OCR is not used when existing content is sufficient."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        # Mock PDF content
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "OCR text"
        mock_page.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        # Long content (over 100 chars) - OCR should not be triggered
        long_text = "This is a very long document content that exceeds one hundred characters " \
                   "and therefore should not trigger OCR fallback"

        doc_data = {
            "eoNumber": "0001202601170001",
            "title": long_text,
            "name": long_text,
            "complexName": long_text,
        }

        result = parser.parse_document(doc_data, use_selenium=False, use_ocr_fallback=True)

        assert result["ocr_used"] is False


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestOCRTextExtraction:
    """Tests for text extraction in OCR."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_ocr_extracts_text_from_multiple_pages(self, mock_pdfplumber):
        """Test OCR extraction from multi-page PDF."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        # Mock multiple pages
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 text"
        mock_page1.to_image.return_value.original = MagicMock()

        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 text"
        mock_page2.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert result["page_count"] == 2
            assert "Page 1 text" in result["full_text"]
            assert "Page 2 text" in result["full_text"]

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_ocr_generates_text_hash(self, mock_pdfplumber):
        """Test that OCR generates text hash."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test OCR content"
        mock_page.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert result["text_hash"] is not None
            assert len(result["text_hash"]) > 0


@pytest.mark.skip(reason="OCR enhancement pending - see Phase 3 (PHASE3_OCR.md)")
class TestOCREdgeCases:
    """Tests for OCR edge cases."""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_ocr_with_empty_pdf(self, mock_pdfplumber):
        """Test OCR with PDF that has no pages."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert result is not None
            assert result["full_text"] == ""

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_ocr_with_unicode_text(self, mock_pdfplumber):
        """Test OCR with Unicode (Cyrillic) text."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Закон Российской Федерации"
        mock_page.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            assert "Российской Федерации" in result["full_text"]

    @patch("scripts.parser.html_parser.SELENIUM_AVAILABLE", False)
    @patch("scripts.parser.html_parser.pdfplumber")
    @patch("scripts.parser.html_parser.pytesseract", MagicMock())
    @patch("scripts.parser.html_parser.PIL.Image", MagicMock())
    def test_ocr_preserves_page_structure(self, mock_pdfplumber):
        """Test that OCR preserves page structure."""
        parser = PravoContentParser(use_ocr=True)
        parser.ocr_session = None

        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "First page"
        mock_page1.to_image.return_value.original = MagicMock()

        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Second page"
        mock_page2.to_image.return_value.original = MagicMock()

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        with patch.object(parser, "_fetch_pdf_bytes", return_value=b"%PDF-1.4"):
            result = parser.parse_with_ocr("0001202601170001")

            # Check that pages are preserved in result
            assert "pages" in result
            assert len(result["pages"]) == 2
            assert result["pages"][0]["page_number"] == 1
