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
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from core.config import PRAVO_API_TIMEOUT
from utils.retry import fetch_with_retry

logger = logging.getLogger(__name__)

# Selenium imports (lazy-loaded to avoid unnecessary imports)
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.info("Selenium not available, will skip Selenium-based content fetching")


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

        # Reusable ChromeDriver instance (lazy initialization)
        self._driver = None

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

    def _get_driver(self):
        """
        Get or create reusable ChromeDriver instance.

        Returns:
            ChromeDriver instance (cached or newly created)
        """
        if self._driver is None:
            options = ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-background-network-true')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--metrics-recording-only')
            options.add_argument('--mute-audio')
            options.add_argument('--no-first-run')
            options.add_argument('--safebrowsing-disable-auto-update')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-notifications')
            options.add_argument('user-agent=Law7/0.1.0')

            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            self._driver.set_page_load_timeout(30)
        return self._driver

    def fetch_with_selenium(self, eo_number: str) -> Optional[str]:
        """
        Fetch document content using Selenium WebDriver to execute JavaScript.

        This follows the pattern used in ygbis project for iframe content extraction:
        1. Navigate to page
        2. Wait for iframe
        3. Switch to iframe
        4. Wait for content to load
        5. Extract page source after JavaScript execution

        Pattern source: ygbis/services/deep_parser/worker.py (lines 200-224)

        Args:
            eo_number: Document eoNumber (e.g., '0001202405140009')

        Returns:
            Extracted document text, or None if failed

        Example:
            >>> parser = PravoContentParser()
            >>> text = parser.fetch_with_selenium('0001202405140009')
            >>> print(len(text))
            1250
        """
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium not available, skipping Selenium-based content fetching")
            return None

        # Log what we're trying to fetch
        logger.info(f"[SELENIUM] Attempting to fetch document: {eo_number}")

        try:
            # Use reusable driver
            driver = self._get_driver()

            # Navigate to page
            url = f"http://actual.pravo.gov.ru/content/content.html#pnum={eo_number}"
            logger.info(f"[SELENIUM] URL: {url}")
            driver.get(url)

            # Handle any alerts (e.g., "Document not found" for PDF-only documents)
            logger.debug(f"[SELENIUM] Page loaded, checking for alerts...")
            try:
                WebDriverWait(driver, 2).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert_text = alert.text
                alert.dismiss()
                logger.warning(f"[SELENIUM] Alert for {eo_number}: {alert_text}")
                logger.info(f"[SELENIUM] Document is PDF-only, falling back to HTML scraper (publication.pravo.gov.ru)")

                # Fall back to html_scraper which handles PDF-only documents
                from scripts.parser.html_scraper import scrape_amendment
                result = scrape_amendment(eo_number)
                if result.get('full_text'):
                    logger.info(f"[SELENIUM] PDF fallback succeeded: {len(result['full_text'])} chars")
                    return result['full_text']
                logger.warning(f"[SELENIUM] PDF fallback also failed for {eo_number}")
                return None
            except TimeoutException:
                logger.debug(f"[SELENIUM] No alert detected, proceeding to iframe...")
                # No alert - continue normally to iframe
                pass

            # Wait for iframe to be present
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe.doc-body"))
            )

            # Switch to iframe
            iframe = driver.find_element(By.CSS_SELECTOR, "iframe.doc-body")
            driver.switch_to.frame(iframe)

            # Wait for content to load (JavaScript execution)
            time.sleep(5)

            # Get page source after JavaScript execution
            page_source = driver.page_source

            if not page_source or len(page_source) < 100:
                logger.warning(f"Iframe content too short for {eo_number}")
                return None

            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')

            # Remove scripts and styles
            for element in soup(['script', 'style', 'noscript']):
                element.decompose()

            # Extract text
            text = soup.get_text(separator='\n', strip=True)

            # Fix encoding: The iframe returns Windows-1251 bytes incorrectly decoded as UTF-8
            # Reverse by encoding as Latin-1 (preserving byte values), then decode as Windows-1251
            try:
                text = text.encode('latin-1').decode('windows-1251')
            except (UnicodeEncodeError, UnicodeDecodeError):
                # If the fix fails, use original text (might already be correct)
                pass

            # Clean up extra whitespace while preserving structure
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)

            logger.info(f"Extracted {len(text)} chars from {eo_number} using Selenium")
            return text

        except Exception as e:
            logger.warning(f"Selenium fetch failed for {eo_number}: {e}")
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
        use_selenium: bool = True,
        use_ocr_fallback: bool = False,
    ) -> Dict[str, Any]:
        """
        Parse document content from API data, with optional Selenium fetching and OCR fallback.

        Args:
            doc_data: Document data from API response
            use_selenium: If True, try Selenium WebDriver for full document text
            use_ocr_fallback: If True, try OCR if content is still insufficient

        Returns:
            Dictionary with parsed content

        Example:
            >>> parser = PravoContentParser()
            >>> doc_data = {"eoNumber": "...", "title": "...", "name": "..."}
            >>> result = parser.parse_document(doc_data)
            >>> print(result['full_text'])
        """
        # First, get API metadata
        result = self.parse_from_api_data(doc_data)

        # Try Selenium for full content
        if use_selenium and result.get("eo_number"):
            content = self.fetch_with_selenium(result["eo_number"])
            if content and len(content) > 100:
                result["full_text"] = content
                result["raw_text"] = content
                result["text_hash"] = self._generate_text_hash(content)
                result["selenium_used"] = True
                result["ocr_used"] = False
                return result

        # If Selenium was skipped or failed, check OCR fallback
        result["selenium_used"] = False

        # If text is still too short and OCR is enabled, try OCR
        if use_ocr_fallback and len(result["full_text"]) < 100 and self.use_ocr:
            logger.info(f"Content too short for {result['eo_number']}, trying OCR")
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
        """Close the HTTP session and cleanup resources."""
        # Close reusable ChromeDriver
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

        # Close HTTP session
        self.session.close()

        # Close OCR session if used
        if self.use_ocr and self.ocr_session:
            self.ocr_session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for quick usage
def parse_pravo_document(
    doc_data: Dict[str, Any],
    use_selenium: bool = True,
    use_ocr: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to parse a pravo.gov.ru document from API data.

    Args:
        doc_data: Document data from API response
        use_selenium: Enable Selenium WebDriver for full document text
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
        return parser.parse_document(doc_data, use_selenium=use_selenium)
