"""
SUDRF scraper for Russian general jurisdiction court decisions.

This module handles scraping of court decisions from the Russian
State Automated System "Justice" (ГАС РФ "Правосудие").

Source: https://sudrf.ru/
Coverage: General jurisdiction courts (civil, criminal, administrative cases)

Reference: tochno-st/sudrfscraper - https://github.com/tochno-st/sudrfscraper

IMPORTANT LIMITATIONS:
-----------------------
SUDRF has extremely strict anti-bot protection:

1. **Geographic Blocking**: SUDRF blocks access from non-Russian IP addresses.
   - Error: "недоступна" (unavailable) - page title shows blocking
   - Solution: Use Russian proxy/VPN or Russian server

2. **Browser Fingerprinting**: Even Selenium with headless Chrome is blocked.
   - The site detects automation tools and returns 403 or "unavailable"
   - Current implementation includes anti-detection measures

3. **CAPTCHA**: SUDRF may require CAPTCHA solving for:
   - Initial search form submission
   - High-volume requests
   - Suspicious activity patterns

RECOMMENDED PRODUCTION SETUP:
-----------------------------
1. **Russian IP Address**: Essential for access
   - Use Russian VPS/proxy service
   - Recommended: Yandex Cloud, Selectel, or other Russian providers

2. **Browser Configuration**:
   - Selenium with Firefox WebDriver (less detection than Chrome)
   - Undetected Chrome Driver (selenium-stealth)
   - Real user agent strings

3. **Rate Limiting**:
   - 10-30 second delays between requests
   - Respect robots.txt
   - Limit concurrent requests

4. **CAPTCHA Handling**:
   - Manual solving for testing
   - 2Captcha / Anti-Captcha services for production
   - Consider human-in-the-loop approach

ALTERNATIVE APPROACHES:
-----------------------
1. **Commercial APIs**: Several services offer SUDRF scraping APIs:
   - parser-api.com/sudrf
   - api-assist.com/api/sudrf
   - api-parser.ru/sudrf-ru

2. **Regional Court Portals**: Some regional courts have independent websites:
   - Example: https://sverdlov--perm.sudrf.ru/
   - May have different access policies

3. **Official API**: SUDRF may offer official API access for organizations:
   - Contact: https://sudrf.ru/ for institutional access

Phase 3 implementation for comprehensive court decision fetching.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from dataclasses import dataclass
import hashlib
import re
from urllib.parse import urljoin
import time

import aiohttp
from bs4 import BeautifulSoup

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
    logging.getLogger(__name__).info("Selenium not available, SUDRF scraper will have limited functionality")

from country_modules.base.scraper import BaseScraper, RawDocument
from core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CourtDecision:
    """Court decision data structure."""

    case_id: str  # Unique case identifier
    case_number: str  # e.g., "2-6665/2023"
    decision_date: date
    court_name: str
    court_code: str  # e.g., "АС"></parameter>
    instance: str  # 'first', 'appeal', 'cassation'
    case_type: str  # 'civil', 'criminal', 'administrative'
    decision_type: str  # 'ruling', 'decision', 'definition'
    title: str
    full_text: str
    summary: str
    source_url: str
    participants: Optional[str] = None  # Plaintiffs, defendants
    judge: Optional[str] = None
    articles_cited: Optional[List[Dict[str, str]]] = None  # Extracted article references


class SudrfScraper(BaseScraper):
    """
    Scraper for Russian general jurisdiction court decisions (SUDRF).

    This scraper fetches court decisions from sudrf.ru, which covers:
    - Civil cases (гражданские дела)
    - Criminal cases (уголовные дела)
    - Administrative cases (дела об административных правонарушениях)

    The scraper focuses on decisions from the last 2 years (2022-2024) to match
    the project's requirements for manageable dataset size and relevance.

    Attributes:
        country_id: ISO 3166-1 alpha-3 code ("RUS")
        country_name: Full country name ("Russia")
        country_code: ISO 3166-1 alpha-2 code ("RU")
    """

    # Country identification
    country_id = "RUS"
    country_name = "Russia"
    country_code = "RU"

    # SUDRF API endpoints (based on sudrfscraper research)
    BASE_URL = "https://sudrf.ru"
    API_URL = "https://sudrf.ru"
    # Official search portal for general jurisdiction courts
    SEARCH_PORTAL_URL = "https://sudrf.ru/index.php?id=300&searchtype=sp"
    # Legacy search URLs (these may return 403 due to anti-bot protection)
    SEARCH_URLS = [
        "https://sudrf.ru/sf.php",           # First instance general jurisdiction (main)
        "https://sudrf.ru/ms.php",           # First instance general jurisdiction (mirsudrf)
        "https://sudrf.ru/ks.php",           # Cassation
        "https://sudrf.ru/vs.php",           # Supreme court
    ]

    # Court instance types
    INSTANCE_TYPES = {
        "first": "Первая инстанция",
        "appeal": "Апелляция",
        "cassation": "Кассация",
        "supreme": "Верховный суд"
    }

    # Case type mappings
    CASE_TYPES = {
        "civil": "Гражданские дела",
        "criminal": "Уголовные дела",
        "administrative": "Дела об административных правонарушениях",
        "bankruptcy": "Дела о банкротстве",
    }

    def __init__(
        self,
        start_date: Optional[date] = None,
        session: Optional[aiohttp.ClientSession] = None,
        use_selenium: bool = True,
    ):
        """
        Initialize the SUDRF scraper.

        Args:
            start_date: Only fetch decisions from this date onwards
            session: Optional aiohttp session for reuse
            use_selenium: Use Selenium WebDriver to bypass anti-bot protection
        """
        self.start_date = start_date or (datetime.now() - timedelta(days=730)).date()
        self._session = session
        self._connector = None
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE

        # Reusable ChromeDriver instance (lazy initialization)
        self._driver = None

        if not SELENIUM_AVAILABLE and use_selenium:
            logger.warning("Selenium requested but not available. Install with: poetry add selenium webdriver-manager")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connector and cookie jar."""
        if self._session and not self._session.closed:
            return self._session

        # Create connector with connection limit
        connector = aiohttp.TCPConnector(limit=10)
        self._connector = connector

        # Create cookie jar for session management
        cookie_jar = aiohttp.CookieJar()

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
            headers=headers,
            cookie_jar=cookie_jar
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
        Get or create reusable ChromeDriver instance.

        Adapted from PravoContentParser pattern for pravo.gov.ru.
        Uses headless Chrome to bypass SUDRF anti-bot protection.

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
            options.add_argument('--disable-background-network-true')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--metrics-recording-only')
            options.add_argument('--mute-audio')
            options.add_argument('--no-first-run')
            options.add_argument('--safebrowsing-disable-auto-update')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            self._driver.set_page_load_timeout(60)
            logger.info("ChromeDriver initialized for SUDRF scraping")
        return self._driver

    async def fetch_manifest(
        self,
        since: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get list of court decisions updated since date.

        Note: SUDRF doesn't have a true "manifest" endpoint. This method
        returns metadata about available search parameters and recent decisions.

        Args:
            since: Only return decisions updated after this date

        Returns:
            Dict with decision list and metadata
        """
        since = since or self.start_date

        logger.info(f"Fetching SUDRF manifest since {since}")

        # Get available courts
        courts_response = await self._get_courts_list()

        # Sample recent decisions
        decisions = await self._fetch_recent_decisions(
            since=since,
            limit=100  # Sample size for manifest
        )

        return {
            "source": "sudrf",
            "since": since.isoformat(),
            "courts": courts_response.get("courts", []),
            "decisions_count": len(decisions),
            "sample_decisions": decisions,
        }

    async def _get_courts_list(self) -> Dict[str, Any]:
        """
        Get list of available courts from SUDRF.

        Returns:
            Dict with courts list
        """
        # SUDRF has a JSON endpoint for court data
        url = f"{self.BASE_URL}/getCourts.php"

        try:
            session = await self._get_session()
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()

                return {"courts": data}
        except Exception as e:
            logger.warning(f"Failed to fetch courts list: {e}")
            return {"courts": []}

    async def _fetch_recent_decisions(
        self,
        since: date,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent court decisions using SUDRF official search portal.

        Uses the official SUDRF search portal at:
        https://sudrf.ru/index.php?id=300&searchtype=sp

        This portal provides search forms for finding court decisions.
        Results include case numbers, dates, and links to full decisions.

        Reference: https://github.com/tochno-st/sudrfscraper

        Args:
            since: Start date for decisions
            limit: Maximum number of decisions to fetch

        Returns:
            List of decision metadata
        """
        logger.info(f"Fetching SUDRF decisions since {since} (limit: {limit})")

        decisions = []

        # Try with Selenium first (bypasses anti-bot protection)
        if self.use_selenium and SELENIUM_AVAILABLE:
            logger.info("Using Selenium to access SUDRF search portal")
            decisions = await self._fetch_with_selenium_portal(since, limit)
            if decisions:
                return decisions[:limit]

        # Fallback to direct HTTP (may get 403)
        logger.info("Selenium not available or failed, trying HTTP directly")
        # Implementation skipped as SUDRF blocks HTTP requests
        return []

    async def _fetch_with_selenium_portal(
        self,
        since: date,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch decisions using Selenium to access the official SUDRF search portal.

        The official portal has forms for searching court decisions by:
        - Case number
        - Date range
        - Court name
        - Participants

        Args:
            since: Start date for decisions
            limit: Maximum number of decisions to fetch

        Returns:
            List of decision metadata
        """
        decisions = []

        try:
            driver = self._get_driver()

            # Navigate to the official search portal
            logger.info(f"Navigating to SUDRF search portal: {self.SEARCH_PORTAL_URL}")
            driver.get(self.SEARCH_PORTAL_URL)

            # Wait for page to load
            time.sleep(15)

            logger.info(f"Page title: {driver.title}")

            # Try to find and fill the search form
            # Look for date input fields or case number search
            try:
                # Look for case number search (search by partial number)
                case_inputs = driver.find_elements(By.XPATH, "//input[@name='num' or @name='case_num' or @name='delo_id' or contains(@placeholder, 'номер')]")
                if case_inputs:
                    logger.info(f"Found {len(case_inputs)} case number input fields")
                    # For now, we'll leave blank to get recent decisions

                # Look for date inputs
                date_inputs = driver.find_elements(By.XPATH, "//input[@type='date' or @type='text'][contains(@name, 'date') or contains(@id, 'date')]")
                logger.info(f"Found {len(date_inputs)} date input fields")

                # Look for search/submit button
                search_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Поиск') or contains(@value, 'Поиск') or @type='submit']")
                if search_buttons:
                    logger.info(f"Found {len(search_buttons)} search buttons")
                    # Click the first search button
                    search_buttons[0].click()
                    logger.info("Clicked search button")

                    # Wait for results to load
                    time.sleep(20)

                    # Get page source with results
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')

                    # Look for result links in the page
                    # SUDRF results typically have links like /modules.php?name=sud_delo&...
                    result_links = soup.find_all("a", href=re.compile(r"/modules\.php\?name=sud_delo"))

                    logger.info(f"Found {len(result_links)} result links")

                    for link in result_links[:limit]:
                        href = link.get("href", "")
                        if href:
                            # Build full URL
                            full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                            # Extract case ID from URL
                            case_id = self._extract_case_id_from_portal(href)

                            # Extract case number from link text
                            case_number = link.get_text(strip=True)
                            if not case_number or len(case_number) < 3:
                                # Try to find it in parent elements
                                parent = link.find_parent("td") or link.find_parent("div") or link.find_parent("li")
                                if parent:
                                    case_text = parent.get_text(strip=True)
                                    # Try to extract case number
                                    number_match = re.search(r"[Дд]ело\s*[№Nn]?\s*([\d\w/-]+)", case_text)
                                    if number_match:
                                        case_number = number_match.group(1)
                                    else:
                                        case_number = case_text[:100]

                            decision_info = {
                                "case_id": case_id,
                                "case_number": case_number[:200] if case_number else f"Case-{case_id}",
                                "url": full_url,
                                "source": "sudrf",
                                "instance": "first",
                                "court_type": "general_jurisdiction",
                                "search_url": self.SEARCH_PORTAL_URL,
                            }

                            if not any(d.get("case_id") == case_id for d in decisions):
                                decisions.append(decision_info)

                    logger.info(f"Extracted {len(decisions)} decisions from search results")

                else:
                    logger.warning("No search button found on page")
                    # Debug: log page structure
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                    buttons = soup.find_all("button")
                    logger.info(f"Page has {len(buttons)} buttons total")
                    for btn in buttons[:5]:
                        logger.debug(f"Button: text={btn.get_text(strip=True)[:50]}, class={btn.get('class')}")

            except Exception as e:
                logger.warning(f"Error interacting with search form: {e}")

        except Exception as e:
            logger.warning(f"Error using Selenium for SUDRF portal: {e}")

        return decisions

    def _extract_case_id_from_portal(self, href: str) -> str:
        """
        Extract case ID from SUDRF portal URL.

        Portal URLs look like:
        /modules.php?name=sud_delo&srv_num=1&name_op=case&case_id=123456...

        Args:
            href: URL path

        Returns:
            Case ID string
        """
        # Extract case_id parameter from URL
        case_id_match = re.search(r"case_id=([^&]+)", href)
        if case_id_match:
            return case_id_match.group(1)

        # Fallback: use hash of URL
        return hashlib.md5(href.encode()).hexdigest()[:8]

    def _extract_case_id(self, href: str) -> str:
        """
        Extract case ID from SUDRF URL.

        Patterns:
        - /sf-12345.html -> 12345
        - /ms/12345/ -> 12345
        - /gs/12345 -> 12345

        Args:
            href: URL path

        Returns:
            Case ID string
        """
        # Match common SUDRF URL patterns
        match = re.search(r"/(sf-|ms/|gs/|vs/)(\d+)", href)
        if match:
            return match.group(2)

        # Fallback: use hash of URL
        return hashlib.md5(href.encode()).hexdigest()[:8]

    async def fetch_document(self, doc_id: str, use_selenium: Optional[bool] = None) -> RawDocument:
        """
        Fetch single court decision by ID.

        Args:
            doc_id: Case number or decision ID
            use_selenium: Override the instance's use_selenium setting

        Returns:
            RawDocument with content and metadata
        """
        logger.info(f"Fetching court decision: {doc_id}")

        # Use Selenium if enabled (either instance setting or override)
        should_use_selenium = use_selenium if use_selenium is not None else self.use_selenium

        # Construct decision URL
        url = f"{self.BASE_URL}/sf-{doc_id}.html"

        if should_use_selenium and SELENIUM_AVAILABLE:
            # Use Selenium to fetch the page (bypasses anti-bot protection)
            try:
                driver = self._get_driver()
                driver.get(url)
                time.sleep(30)  # Wait for JavaScript execution
                html_content = driver.page_source.encode('utf-8')
            except Exception as e:
                logger.warning(f"Selenium fetch failed for {doc_id}, falling back to HTTP: {e}")
                # Fallback to HTTP
                session = await self._get_session()
                async with session.get(url) as response:
                    response.raise_for_status()
                    html_content = await response.read()
        else:
            # Use HTTP aiohttp
            session = await self._get_session()
            async with session.get(url) as response:
                response.raise_for_status()
                html_content = await response.read()

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract decision content
        decision_data = self._parse_decision_page(soup, doc_id, url)

        # Generate content
        content = decision_data.get("full_text", "")

        # Generate hash
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        return RawDocument(
            doc_id=doc_id,
            url=url,
            content=content.encode('utf-8'),
            content_type="text/html",
            metadata=decision_data
        )

    def _parse_decision_page(
        self,
        soup: BeautifulSoup,
        doc_id: str,
        url: str
    ) -> Dict[str, Any]:
        """
        Parse court decision HTML page.

        Args:
            soup: BeautifulSoup of the decision page
            doc_id: Document/case ID
            url: Source URL

        Returns:
            Parsed decision data
        """
        # Extract case information
        case_number = doc_id
        court_name = ""
        decision_date = None
        title = ""
        full_text = ""
        participants = ""
        judge = ""

        # Try to find decision content in various containers
        # SUDRF pages have complex HTML structure

        # Look for decision text in common containers
        text_containers = [
            soup.find('div', class_=lambda x: x and 'decision' in x.lower() if x else False),
            soup.find('div', class_=lambda x: x and 'text' in x.lower() if x else False),
            soup.find('div', class_='card'),
            soup.find('article'),
        ]

        for container in text_containers:
            if container:
                # Extract title
                title_elem = container.find(['h1', 'h2', 'h3'])
                if title_elem:
                    title = title_elem.get_text(strip=True)

                # Extract text content
                # Remove scripts, styles, navigation
                for elem in container(['script', 'style', 'nav', 'header', 'footer']):
                    elem.decompose()

                full_text = container.get_text(separator='\n', strip=True)

                if len(full_text) > 100:  # Only if we got meaningful content
                    break

        # If no content found, try body
        if len(full_text) < 100:
            body = soup.find('body')
            if body:
                # Remove unwanted elements
                for elem in body(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    elem.decompose()
                full_text = body.get_text(separator='\n', strip=True)

        # Clean up text
        lines = []
        for line in full_text.split('\n'):
            line = line.strip()
            if line and len(line) > 3:
                lines.append(line)

        full_text = '\n'.join(lines)

        # Extract metadata from meta tags or page elements
        meta_title = soup.find('title')
        if meta_title:
            title = title or meta_title.get_text(strip=True)

        return {
            'case_id': doc_id,
            'case_number': case_number,
            'decision_date': decision_date,
            'court_name': court_name,
            'instance': 'first',  # Default
            'case_type': 'civil',  # Default
            'title': title,
            'full_text': full_text,
            'summary': full_text[:500] + '...' if len(full_text) > 500 else full_text,
            'participants': participants,
            'judge': judge,
            'source_url': url,
        }

    async def fetch_updates(
        self,
        since: date
    ) -> List[RawDocument]:
        """
        Fetch all court decisions updated since date.

        Args:
            since: Start date for updates

        Returns:
            List of RawDocument objects
        """
        logger.info(f"Fetching SUDRF updates since {since}")

        # Get manifest with decisions
        manifest = await self.fetch_manifest(since=since)
        decisions = manifest.get("sample_decisions", [])

        # Fetch full content for each decision
        documents = []
        for decision_meta in decisions:
            doc_id = decision_meta.get('case_id') or decision_meta.get('case_number')
            if doc_id:
                try:
                    doc = await self.fetch_document(doc_id)
                    documents.append(doc)

                    # Rate limiting between requests
                    await asyncio.sleep(5)  # 5 second delay per request

                except Exception as e:
                    logger.warning(f"Failed to fetch {doc_id}: {e}")
                    continue

        logger.info(f"Fetched {len(documents)} court decisions from SUDRF")
        return documents

    async def verify_document(
        self,
        doc_id: str,
        content_hash: str
    ) -> bool:
        """
        Verify document content matches hash.

        Args:
            doc_id: Document identifier
            content_hash: Expected hash value

        Returns:
            bool: True if hash matches
        """
        doc = await self.fetch_document(doc_id)
        actual_hash = hashlib.sha256(doc.content).hexdigest()
        return actual_hash == content_hash


# Convenience function for quick usage
async def fetch_court_decisions(
    start_date: str,
    end_date: str,
) -> List[CourtDecision]:
    """
    Convenience function to fetch court decisions for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of court decisions
    """
    async with SudrfScraper() as scraper:
        since = datetime.strptime(start_date, "%Y-%m-%d").date()
        updates = await scraper.fetch_updates(since=since)

        decisions = []
        for raw_doc in updates:
            # Convert RawDocument to CourtDecision
            decisions.append(CourtDecision(
                case_id=raw_doc.doc_id,
                case_number=raw_doc.metadata.get('case_number', raw_doc.doc_id),
                decision_date=datetime.now(),  # Would need to parse from content
                court_name=raw_doc.metadata.get('court_name', ''),
                court_code='SUDRF',
                instance='first',
                case_type='civil',
                decision_type='ruling',
                title=raw_doc.metadata.get('title', ''),
                full_text=raw_doc.content.decode('utf-8', errors='ignore'),
                summary=raw_doc.metadata.get('summary', ''),
                source_url=raw_doc.url,
            ))

        return decisions
