"""
Court decision scraper for Russian Supreme Court and Constitutional Court.

This module handles scraping of court decisions from official court portals.
Phase 7C focuses on:
- Supreme Court: Plenary resolutions (Постановления Пленума), practice reviews
- Constitutional Court: Rulings (Постановления), determinations (Определения)

Sources:
- Supreme Court: https://vsrf.ru
- Constitutional Court: http://www.ksrf.ru

IMPORTANT: vsrf.ru uses JavaScript (Bitrix CMS) to load documents dynamically.
This requires Selenium WebDriver to wait for AJAX content to load.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from dataclasses import dataclass
import hashlib
import re
import time
import aiohttp
from bs4 import BeautifulSoup

# Selenium imports (lazy-loaded)
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.getLogger(__name__).info("Selenium not available, vsrf.ru scraper will have limited functionality")

from country_modules.base.scraper import BaseScraper, RawDocument
from core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CourtDecision:
    """Court decision data structure."""

    court_type: str  # 'supreme', 'constitutional'
    decision_type: str  # 'plenary_resolution', 'ruling', 'determination', 'review'
    case_number: str
    decision_date: date
    title: str
    summary: Optional[str] = None
    full_text: Optional[str] = None
    legal_issues: Optional[List[str]] = None
    articles_interpreted: Optional[Dict[str, List[str]]] = None
    binding_nature: str = "mandatory"
    source_url: Optional[str] = None


@dataclass
class PracticeReview:
    """Practice review (Обзор судебной практики) data structure."""

    court_type: str  # 'supreme', 'constitutional'
    review_title: str
    publication_date: date
    period_covered: Optional[str] = None
    content: Optional[str] = None
    key_conclusions: Optional[List[str]] = None
    common_errors: Optional[List[str]] = None
    correct_approaches: Optional[List[str]] = None
    cases_analyzed: Optional[int] = None
    source_url: Optional[str] = None


@dataclass
class LegalPosition:
    """Legal position from Constitutional Court."""

    decision_id: str
    position_text: str
    constitutional_basis: Optional[List[str]] = None
    laws_affected: Optional[List[str]] = None
    position_date: Optional[date] = None
    still_valid: bool = True


class CourtScraper(BaseScraper):
    """
    Scraper for Russian court decisions.

    Phase 7C focuses on Supreme Court and Constitutional Court.
    """

    # vsrf.ru URLs (Supreme Court)
    VSRF_BASE_URL = "https://vsrf.ru"
    VSRF_DOCUMENTS_URL = "https://vsrf.ru/documents/own/"
    VSRF_PRACTICE_URL = "https://vsrf.ru/documents/practice/"

    def __init__(self, court_type: str = "supreme"):
        """
        Initialize court scraper.

        Args:
            court_type: 'supreme' or 'constitutional'
        """
        if court_type not in ("supreme", "constitutional"):
            raise ValueError("court_type must be 'supreme' or 'constitutional'")

        self.court_type = court_type
        self.base_url = self._get_court_url(court_type)

        settings = get_settings()
        self.timeout = settings.http_timeout
        self.batch_size = settings.batch_size
        self._session = None
        self._connector = None
        self._driver = None  # ChromeDriver for JavaScript-rendered pages

    def _get_court_url(self, court_type: str) -> str:
        """Get base URL for court type."""
        urls = {
            "supreme": "https://vsrf.ru",
            "constitutional": "http://www.ksrf.ru"
        }
        return urls.get(court_type, "")

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create aiohttp session with proper headers for vsrf.ru.

        vsrf.ru requires browser-like headers to avoid 403 Forbidden.
        """
        if self._session and not self._session.closed:
            return self._session

        # Create connector with connection limit
        connector = aiohttp.TCPConnector(limit=10)
        self._connector = connector

        # vsrf.ru requires proper browser headers
        timeout = aiohttp.ClientTimeout(total=60, connect=30)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.6",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self._session

    async def close(self):
        """Close the session, connector, and ChromeDriver."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close()
        if self._driver:
            try:
                self._driver.quit()
                logger.debug("ChromeDriver closed")
            except Exception:
                pass
            self._driver = None

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _get_driver(self):
        """
        Get or create reusable ChromeDriver instance for vsrf.ru.

        vsrf.ru uses JavaScript (Bitrix CMS) to load documents dynamically.
        This requires Selenium to wait for AJAX content.

        Returns:
            ChromeDriver instance (cached or newly created)
        """
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium not available. Install with: poetry add selenium webdriver-manager")

        if self._driver is None:
            options = ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-notifications')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            self._driver.set_page_load_timeout(60)
            logger.info("ChromeDriver initialized for vsrf.ru scraping")
        return self._driver

    @property
    def country_id(self) -> str:
        return "RUS"

    @property
    def country_name(self) -> str:
        return "Russia"

    @property
    def country_code(self) -> str:
        return "RU"

    async def fetch_manifest(self, since: Optional[date] = None) -> Dict[str, Any]:
        """
        Get list of court decisions updated since date.

        Args:
            since: Only return decisions published after this date.

        Returns:
            Dict with decision list and metadata
        """
        logger.info(f"Fetching {self.court_type} court manifest since {since}")

        # TODO: Implement actual API call to court portal
        # Supreme Court: https://vsrf.gov.ru/documents/ (different document types)
        # Constitutional Court: http://www.ksrf.ru/ru/Decision/

        manifest = {
            "court_type": self.court_type,
            "decisions": [],
            "last_updated": date.today().isoformat(),
            "metadata": {
                "base_url": self.base_url,
                "since": since.isoformat() if since else None,
            }
        }

        logger.warning(f"{self.court_type} court manifest fetching not yet implemented")
        return manifest

    async def fetch_document(self, doc_id: str) -> RawDocument:
        """
        Fetch single court decision by ID.

        Args:
            doc_id: Document identifier (court-specific format)

        Returns:
            RawDocument with content and metadata
        """
        # TODO: Implement document fetching from court portal
        raise NotImplementedError(
            "Court document fetching requires court-specific implementation. "
            "See PHASE5_COURTS.md for implementation details."
        )

    async def fetch_updates(self, since: date) -> List[RawDocument]:
        """
        Fetch all court decisions published since date.

        Args:
            since: Start date for updates

        Returns:
            List of RawDocument objects
        """
        logger.info(f"Fetching {self.court_type} court updates since {since}")

        # TODO: Implement batch fetching
        # For Phase 7C, we need to:
        # 1. Query court portal's document listings
        # 2. Filter by decision type and date range
        # 3. Extract document metadata and URLs

        logger.warning(f"{self.court_type} court updates fetching not yet implemented")
        return []

    async def verify_document(self, doc_id: str, content_hash: str) -> bool:
        """
        Verify court decision content matches hash.

        Args:
            doc_id: Document identifier
            content_hash: Expected hash value (SHA-256)

        Returns:
            bool: True if hash matches
        """
        doc = await self.fetch_document(doc_id)
        computed_hash = hashlib.sha256(doc.content).hexdigest()
        return computed_hash == content_hash

    async def fetch_supreme_plenary_resolutions(
        self,
        since: Optional[date] = None,
        year: Optional[int] = None,
        limit: Optional[int] = None,
        use_selenium: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch Supreme Court plenary resolutions (Постановления Пленума ВС РФ).

        vsrf.ru uses JavaScript (Bitrix CMS) to load documents dynamically.
        Selenium is required to wait for AJAX content to load.

        Args:
            since: Only fetch resolutions after this date
            year: Filter by specific year (e.g., 2026)
            limit: Maximum number of resolutions to fetch
            use_selenium: Use Selenium WebDriver (recommended for vsrf.ru)

        Returns:
            List of plenary resolution metadata with URLs
        """
        if self.court_type != "supreme":
            raise ValueError("This method requires Supreme Court scraper")

        # Default to current year if not specified
        if year is None:
            year = datetime.now().year

        logger.info(f"Fetching Supreme Court plenary resolutions for {year}")

        # Try Selenium first (recommended for vsrf.ru)
        if use_selenium and SELENIUM_AVAILABLE:
            logger.info("Using Selenium to fetch vsrf.ru (JavaScript-loaded content)")
            resolutions = await self._fetch_supreme_plenary_with_selenium(year, limit)
            if resolutions:
                return resolutions

        # Fallback to HTTP (may not work for AJAX-loaded content)
        logger.warning("Selenium not available or failed, trying HTTP (may not find documents)")
        return await self._fetch_supreme_plenary_http(year, limit)

    async def _fetch_supreme_plenary_with_selenium(
        self,
        year: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch Supreme Court plenary resolutions using Selenium.

        vsrf.ru uses Bitrix CMS with AJAX to load documents.
        Selenium waits for JavaScript to execute and content to load.

        Args:
            year: Year to fetch
            limit: Maximum number of resolutions

        Returns:
            List of resolution metadata
        """
        resolutions = []

        try:
            driver = self._get_driver()

            # Construct URL for Plenary Resolutions by year
            # Use date_start parameter to get ALL documents from that year onwards
            # before=1000 ensures we get maximum documents (up to ~600-700 per query)
            url = f"{self.VSRF_DOCUMENTS_URL}?category=resolutions_plenum_supreme_court_russian&date_start=01.01.{year}&before=1000"
            logger.info(f"Navigating to: {url}")

            # Navigate to page
            driver.get(url)

            # Wait for AJAX content to load (vsrf.ru uses Bitrix with AJAX)
            # The "vs-ajax-request-indicator" class shows when loading
            # Need to wait for the document list to appear
            logger.info("Waiting for AJAX content to load...")
            time.sleep(25)  # Longer initial wait

            # Wait for document list to appear
            # Look for the vs-items-list-default or vs-wrapper-items class
            for i in range(30):  # Max 30 seconds additional wait
                try:
                    # Check if document list is loaded
                    doc_lists = driver.find_elements("css selector", ".vs-items-list-default, .vs-wrapper-items, .vs-items")
                    if doc_lists:
                        logger.debug(f"Document list loaded after {25 + i} seconds")
                        break
                    # Check if loading indicator is gone
                    loading_indicators = driver.find_elements("css selector", ".vs-ajax-request-indicator.loading")
                    if not loading_indicators and doc_lists:
                        logger.debug(f"AJAX complete after {25 + i} seconds")
                        break
                except:
                    pass

                time.sleep(1)
            else:
                logger.warning("Document list may not have loaded, proceeding anyway")

            # Get page source after JavaScript execution
            html = driver.page_source
            logger.info(f"Fetched {len(html)} chars from vsrf.ru (with Selenium)")

            # Parse HTML for document links
            soup = BeautifulSoup(html, 'html.parser')

            # vsrf.ru documents can have various URL patterns
            # Look for any links that might be documents
            all_links = soup.find_all("a", href=True)

            logger.info(f"Found {len(all_links)} total links on page")

            # Look for document-like links
            # IMPORTANT: Process ALL links first, then apply limit at the end
            # The numeric document links appear later in the HTML, so we can't
            # slice [:limit] before filtering.
            numeric_link_count = 0
            for link in all_links:  # Process ALL links
                try:
                    href = link.get("href", "")
                    if not href:
                        continue

                    # Skip non-document links and navigation
                    if any(skip in href for skip in [
                        "/press_center/", "/about/", "/appeals/", "/contacts/", "/search/",
                        "http", "vk.com", "youtube", "rutube", "flickr", "max.ru",
                        "/documents$",  # Generic documents index page
                        "/documents/?$",  # Generic documents index page with trailing slash
                        "/documents/own",  # Generic own page without ID
                        "/lk/",  # Personal cabinet
                        "#",  # Anchor links
                    ]):
                        continue

                    # vsrf.ru uses relative numeric URLs for documents (e.g., "35296/", "35295/")
                    # These are relative to /documents/own/ directory
                    # Match: pure numeric URLs like "12345/" or "12345"
                    if re.match(r'^\d+/$', href):
                        numeric_link_count += 1
                        doc_id = href.strip('/')
                        # Build full URL: /documents/own/35296/
                        full_url = f"{self.VSRF_DOCUMENTS_URL}{doc_id}/"
                        logger.debug(f"Found numeric link: {href} -> {doc_id}")
                    elif re.match(r'^\d+$', href):
                        numeric_link_count += 1
                        doc_id = href
                        # Build full URL: /documents/own/35296
                        full_url = f"{self.VSRF_DOCUMENTS_URL}{doc_id}/"
                        logger.debug(f"Found numeric link (no slash): {href} -> {doc_id}")
                    # Also match direct /documents/own/12345 pattern
                    elif re.search(r'/documents/own/\d+', href):
                        doc_id_match = re.search(r'/documents/own/(\d+)', href)
                        doc_id = doc_id_match.group(1)
                        full_url = f"{self.VSRF_BASE_URL}{href}" if href.startswith("/") else href
                        logger.debug(f"Found direct pattern link: {href} -> {doc_id}")
                    else:
                        continue

                    # Extract title from link text
                    title = link.get_text(strip=True)

                    # Clean up title (remove extra whitespace)
                    title = re.sub(r'\s+', ' ', title).strip()

                    logger.debug(f"Doc {doc_id}: title length={len(title)}, title={title[:80]}")

                    # Skip if title is too short or generic
                    if not title or len(title) < 10 or title in ["Документы", "Documents", "", "/"]:
                        logger.debug(f"Skipped doc {doc_id}: title too short or generic")
                        continue

                    resolution_info = {
                        "doc_id": doc_id,
                        "title": title[:300],
                        "url": full_url,
                        "court_type": "supreme",
                        "decision_type": "plenary_resolution",
                        "source": "vsrf",
                        "category": "resolutions_plenum_supreme_court_russian",
                        "year": year,
                    }

                    # Skip duplicates
                    if not any(r.get("doc_id") == doc_id for r in resolutions):
                        resolutions.append(resolution_info)
                        logger.info(f"Added resolution {doc_id}: {title[:80]}")

                    # Apply limit AFTER finding valid resolutions
                    if limit and len(resolutions) >= limit:
                        logger.info(f"Reached limit of {limit} resolutions")
                        break

                except Exception as e:
                    logger.debug(f"Error parsing document link: {e}")
                    continue

            logger.info(f"Found {numeric_link_count} numeric links, extracted {len(resolutions)} resolutions with Selenium")

        except Exception as e:
            logger.error(f"Failed to fetch with Selenium: {e}")

        return resolutions

    async def _fetch_supreme_plenary_http(
        self,
        year: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch Supreme Court plenary resolutions using HTTP (fallback).

        Note: This may not work because vsrf.ru loads documents via JavaScript.

        Args:
            year: Year to fetch
            limit: Maximum number of resolutions

        Returns:
            List of resolution metadata
        """
        resolutions = []
        session = await self._get_session()

        # Construct URL for Plenary Resolutions by year
        # Use date_start parameter to get ALL documents from that year onwards
        url = f"{self.VSRF_DOCUMENTS_URL}?category=resolutions_plenum_supreme_court_russian&date_start=01.01.{year}&before=1000"
        logger.info(f"Fetching from: {url}")

        try:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()

            logger.info(f"Fetched {len(html)} chars from vsrf.ru (HTTP)")

            # Parse HTML for document links
            soup = BeautifulSoup(html, 'html.parser')

            # Look for document links
            doc_links = soup.find_all("a", href=re.compile(r"/documents/own/\d+/"))

            logger.info(f"Found {len(doc_links)} document links (HTTP)")

            for link in doc_links[:limit] if limit else doc_links:
                try:
                    href = link.get("href", "")
                    if not href:
                        continue

                    # Build full URL
                    full_url = f"{self.VSRF_BASE_URL}{href}" if href.startswith("/") else href

                    # Extract document ID from URL
                    doc_id_match = re.search(r"/documents/own/(\d+)/", href)
                    doc_id = doc_id_match.group(1) if doc_id_match else hashlib.md5(href.encode()).hexdigest()[:8]

                    # Extract title from link text
                    title = link.get_text(strip=True)

                    resolution_info = {
                        "doc_id": doc_id,
                        "title": title[:300] if title else f"Resolution {doc_id}",
                        "url": full_url,
                        "court_type": "supreme",
                        "decision_type": "plenary_resolution",
                        "source": "vsrf",
                        "category": "resolutions_plenum_supreme_court_russian",
                        "year": year,
                    }

                    # Skip duplicates
                    if not any(r.get("doc_id") == doc_id for r in resolutions):
                        resolutions.append(resolution_info)

                except Exception as e:
                    logger.debug(f"Error parsing document link: {e}")
                    continue

            logger.info(f"Extracted {len(resolutions)} Supreme Court plenary resolutions (HTTP)")

            # Rate limiting
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Failed to fetch Supreme Court plenary resolutions (HTTP): {e}")

        return resolutions

    def _extract_russian_date(self, date_text: str) -> Optional[date]:
        """
        Extract date from Russian text.

        Examples:
        - "7 ноября 2025"
        - "28.07.2025"
        - "28 июля 2025 г."

        Args:
            date_text: Text containing date

        Returns:
            Date object or None
        """
        # Russian month names
        months = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
        }

        # Try "DD Month YYYY" format
        for month_name, month_num in months.items():
            if month_name in date_text.lower():
                parts = date_text.lower().replace(month_name, " ").split()
                if len(parts) >= 2:
                    try:
                        day = int(parts[0])
                        year = int(parts[-1])
                        return date(year, month_num, day)
                    except (ValueError, IndexError):
                        pass

        # Try DD.MM.YYYY format
        dot_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", date_text)
        if dot_match:
            try:
                return date(int(dot_match.group(3)), int(dot_match.group(2)), int(dot_match.group(1)))
            except ValueError:
                pass

        return None

    async def fetch_supreme_practice_reviews(
        self,
        year: Optional[int] = None,
        quarter: Optional[int] = None
    ) -> List[PracticeReview]:
        """
        Fetch Supreme Court practice reviews (Обзоры судебной практики).

        Args:
            year: Filter by year
            quarter: Filter by quarter (1-4)

        Returns:
            List of practice reviews
        """
        if self.court_type != "supreme":
            raise ValueError("This method requires Supreme Court scraper")

        logger.info(f"Fetching Supreme Court practice reviews for {year} Q{quarter}")

        # TODO: Implement scraping from https://vsrf.gov.ru/documents/practice/
        # Pattern: Обзоры судебной практики Верховного Суда РФ

        # Placeholder structure
        reviews = []

        logger.warning("Supreme Court practice reviews fetching not yet implemented")
        return reviews

    async def fetch_constitutional_rulings(self, since: Optional[date] = None) -> List[CourtDecision]:
        """
        Fetch Constitutional Court rulings (Постановления КС РФ).

        Args:
            since: Only fetch rulings after this date

        Returns:
            List of Constitutional Court rulings
        """
        if self.court_type != "constitutional":
            raise ValueError("This method requires Constitutional Court scraper")

        logger.info(f"Fetching Constitutional Court rulings since {since}")

        # TODO: Implement scraping from http://www.ksrf.ru/ru/Decision/
        # Pattern: Постановления Конституционного Суда РФ

        # Placeholder structure
        rulings = []

        logger.warning("Constitutional Court rulings fetching not yet implemented")
        return rulings

    async def fetch_constitutional_determinations(
        self,
        with_positions: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch Constitutional Court determinations (Определения) with legal positions.

        Args:
            with_positions: Only fetch determinations with significant legal positions

        Returns:
            List of determinations with legal positions
        """
        if self.court_type != "constitutional":
            raise ValueError("This method requires Constitutional Court scraper")

        logger.info(f"Fetching Constitutional Court determinations (with_positions={with_positions})")

        # TODO: Implement scraping from http://www.ksrf.ru/ru/Decision/
        # Pattern: Определения КС РФ (с значительными правовыми позициями)

        # Placeholder structure
        determinations = []

        logger.warning("Constitutional Court determinations fetching not yet implemented")
        return determinations

    async def fetch_all_phase7c_court_data(self) -> Dict[str, Any]:
        """
        Fetch all Phase 7C court data (Supreme + Constitutional).

        Returns:
            Dict with all court data for Phase 7C
        """
        logger.info("Fetching all Phase 7C court data")

        # Supreme Court data
        supreme_scraper = CourtScraper("supreme")
        supreme_data = {
            "plenary_resolutions": await supreme_scraper.fetch_supreme_plenary_resolutions(),
            "practice_reviews": await supreme_scraper.fetch_supreme_practice_reviews(),
        }

        # Constitutional Court data
        constitutional_scraper = CourtScraper("constitutional")
        constitutional_data = {
            "rulings": await constitutional_scraper.fetch_constitutional_rulings(),
            "determinations": await constitutional_scraper.fetch_constitutional_determinations(),
        }

        return {
            "supreme_court": supreme_data,
            "constitutional_court": constitutional_data,
        }


def get_court_urls() -> Dict[str, str]:
    """
    Get URLs for court portals.

    Returns:
        Dict mapping court_type to base URL
    """
    return {
        "supreme": "https://vsrf.gov.ru",
        "constitutional": "http://www.ksrf.ru"
    }


def get_supreme_decision_types() -> List[str]:
    """
    Get list of Supreme Court decision types for Phase 7C.

    Returns:
        List of decision type identifiers
    """
    return [
        "plenary_resolution",  # Постановления Пленума
        "practice_review",      # Обзоры судебной практики
        "presidium_resolution", # Постановления Президиума
        "judicial_college_ruling", # Определения Судебной коллегии
    ]


def get_constitutional_decision_types() -> List[str]:
    """
    Get list of Constitutional Court decision types for Phase 7C.

    Returns:
        List of decision type identifiers
    """
    return [
        "ruling",       # Постановления
        "determination", # Определения
        "order",        # Распоряжения
    ]
