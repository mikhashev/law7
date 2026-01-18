"""
Document content parser for pravo.gov.ru.

Since pravo.gov.ru PDFs are scanned images (not text-based), this parser:
1. Uses API metadata (title, name, complexName) as primary text source
2. Provides optional OCR support for scanned PDFs (requires Tesseract)
3. Handles both cases gracefully

Based on ygbis patterns for error handling and logging.
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

import requests

from core.config import PRAVO_API_TIMEOUT
from utils.retry import fetch_with_retry

logger = logging.getLogger(__name__)


class PravoContentParser:
    """
    Parser for pravo.gov.ru document content.

    Handles both metadata extraction and optional OCR for scanned PDFs.
    """

    # Base URL for pravo.gov.ru
    BASE_URL = "http://publication.pravo.gov.ru"

    def __init__(
        self,
        use_ocr: bool = False,
        timeout: int = PRAVO_API_TIMEOUT,
    ):
        """
        Initialize the content parser.

        Args:
            use_ocr: Enable OCR for scanned PDFs (requires Tesseract)
            timeout: Request timeout in seconds
        """
        self.use_ocr = use_ocr
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Law7/0.1.0"})

        # Initialize OCR if enabled
        self.tesseract = None
        if use_ocr:
            try:
                import pytesseract
                self.tesseract = pytesseract
                from PIL import Image
                self.PIL = Image
                logger.info("OCR enabled: pytesseract available")
            except ImportError as e:
                logger.warning(f"OCR requested but dependencies not available: {e}")
                self.use_ocr = False

    def get_pdf_url(self, eo_number: str) -> str:
        """Get the direct PDF download URL for an eoNumber."""
        return f"{self.BASE_URL}/file/pdf?eoNumber={eo_number}"

    def get_document_view_url(self, eo_number: str) -> str:
        """Get the document view URL for an eoNumber."""
        return f"{self.BASE_URL}/Document/View/{eo_number}"

    def parse_from_api_data(
        self,
        doc_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Parse document content from API response data.

        This is the primary method for extracting content from pravo.gov.ru.
        Since PDFs are scanned images, we use the API metadata as the text source.

        Args:
            doc_data: Document data from API response

        Returns:
            Dictionary with content fields:
                - full_text: Combined text from title/name/complexName
                - raw_text: Raw combined text
                - title: Document title
                - name: Document name
                - complex_name: Full name with date/number
                - pdf_url: PDF download URL
                - html_url: Document view URL
                - text_hash: Hash of the text for change detection
        """
        eo_number = doc_data.get("eoNumber", "")

        # Extract text fields from API data
        title = self._clean_html_text(doc_data.get("title", ""))
        name = doc_data.get("name", "")
        complex_name = doc_data.get("complexName", "")

        # Combine all available text fields
        text_parts = []
        if complex_name:
            text_parts.append(complex_name)
        if name and name != complex_name:
            text_parts.append(name)
        if title and title not in " ".join(text_parts):
            text_parts.append(self._clean_html_text(title))

        full_text = "\n\n".join(text_parts) if text_parts else ""
        raw_text = full_text

        # Generate text hash for change detection
        text_hash = self._generate_text_hash(full_text)

        # Build URLs
        pdf_url = self.get_pdf_url(eo_number)
        html_url = self.get_document_view_url(eo_number)

        return {
            "eo_number": eo_number,
            "full_text": full_text,
            "raw_text": raw_text,
            "title": title,
            "name": name,
            "complex_name": complex_name,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "text_hash": text_hash,
        }

    def parse_with_ocr(
        self,
        eo_number: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse document content using OCR on the PDF.

        This downloads the PDF and performs OCR on each page.
        Requires Tesseract OCR to be installed on the system.

        Args:
            eo_number: Document eoNumber

        Returns:
            Dictionary with OCR-extracted content, or None if failed
        """
        if not self.use_ocr:
            logger.warning("OCR not enabled, skipping PDF OCR")
            return None

        logger.info(f"Performing OCR on document: {eo_number}")

        try:
            import io
            import pdfplumber

            # Fetch PDF
            pdf_bytes = self._fetch_pdf_bytes(eo_number)
            if not pdf_bytes:
                return None

            # Open PDF and extract images for OCR
            full_text = []
            page_texts = []

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for i, page in enumerate(pdf.pages):
                    # Try to get text directly first
                    text = page.extract_text()

                    # If no text, try OCR on page image
                    if not text or len(text.strip()) < 10:
                        # Convert page to image
                        image = page.to_image()
                        pil_image = image.original

                        # Perform OCR with Russian language
                        text = self.tesseract.image_to_string(
                            pil_image,
                            lang="rus+eng",
                            config="--psm 6"
                        )

                    if text.strip():
                        page_texts.append({
                            "page_number": i + 1,
                            "text": text.strip(),
                        })
                        full_text.append(text.strip())

            return {
                "eo_number": eo_number,
                "full_text": "\n\n".join(full_text),
                "raw_text": "\n\n".join(full_text),
                "page_count": len(page_texts),
                "pages": page_texts,
                "text_hash": self._generate_text_hash("\n\n".join(full_text)),
            }

        except Exception as e:
            logger.error(f"OCR failed for {eo_number}: {e}")
            return None

    def _fetch_pdf_bytes(self, eo_number: str) -> Optional[bytes]:
        """Fetch PDF bytes for a document."""
        url = self.get_pdf_url(eo_number)

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            if not response.content[:4] == b"%PDF":
                logger.warning(f"Response for {eo_number} is not a valid PDF")
                return None

            return response.content
        except Exception as e:
            logger.error(f"Failed to fetch PDF for {eo_number}: {e}")
            return None

    def _clean_html_text(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _generate_text_hash(self, text: str) -> str:
        """Generate a hash of the text for change detection."""
        if not text:
            return ""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def parse_document(
        self,
        doc_data: Dict[str, Any],
        use_ocr_fallback: bool = False,
    ) -> Dict[str, Any]:
        """
        Parse document content from API data, with optional OCR fallback.

        Args:
            doc_data: Document data from API response
            use_ocr_fallback: If True, try OCR if API metadata is insufficient

        Returns:
            Dictionary with parsed content

        Example:
            >>> parser = PravoContentParser()
            >>> doc_data = {"eoNumber": "...", "title": "...", "name": "..."}
            >>> result = parser.parse_document(doc_data)
            >>> print(result['full_text'])
        """
        # First, try API metadata
        result = self.parse_from_api_data(doc_data)

        # If text is too short and OCR is enabled, try OCR
        if use_ocr_fallback and len(result["full_text"]) < 100 and self.use_ocr:
            logger.info(f"API text too short for {result['eo_number']}, trying OCR")
            ocr_result = self.parse_with_ocr(result["eo_number"])
            if ocr_result and len(ocr_result["full_text"]) > len(result["full_text"]):
                result["full_text"] = ocr_result["full_text"]
                result["raw_text"] = ocr_result["raw_text"]
                result["ocr_used"] = True
            else:
                result["ocr_used"] = False
        else:
            result["ocr_used"] = False

        return result

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for quick usage
def parse_pravo_document(
    doc_data: Dict[str, Any],
    use_ocr: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to parse a pravo.gov.ru document from API data.

    Args:
        doc_data: Document data from API response
        use_ocr: Enable OCR for scanned PDFs

    Returns:
        Parsed document content

    Example:
        >>> from parser.html_parser import parse_pravo_document
        >>> doc_data = {
        ...     "eoNumber": "0001202601170001",
        ...     "title": "Распоряжение Правительства...",
        ...     "name": "О присвоении классных чинов...",
        ... }
        >>> result = parse_pravo_document(doc_data)
        >>> print(result['full_text'])
    """
    with PravoContentParser(use_ocr=use_ocr) as parser:
        return parser.parse_document(doc_data)
