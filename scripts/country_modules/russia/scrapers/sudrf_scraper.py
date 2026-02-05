"""
SUDRF scraper for Russian general jurisdiction court decisions.

This module handles scraping of court decisions from the Russian
State Automated System "Justice" (ГАС РФ "Правосудие").

Source: https://sudrf.ru/
Coverage: General jurisdiction courts (civil, criminal, administrative cases)

Reference: tochno-st/sudrfscraper - https://github.com/tochno-st/sudrfscraper

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

import aiohttp
from bs4 import BeautifulSoup

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
    API_URL = "https://sudrf.ru/fresh/ajax"

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
    ):
        """
        Initialize the SUDRF scraper.

        Args:
            start_date: Only fetch decisions from this date onwards
            session: Optional aiohttp session for reuse
        """
        self.start_date = start_date or (datetime.now() - timedelta(days=730)).date()
        self._session = session
        self._connector = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connector."""
        if self._session and not self._session.closed:
            return self._session

        # Create connector with connection limit
        connector = aiohttp.TCPConnector(limit=10)
        self._connector = connector

        timeout = aiohttp.ClientTimeout(total=60, connect=30)
        headers = {
            "User-Agent": "Law7/0.1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.6",
        }

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self._session

    async def close(self):
        """Close the session and connector."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close()

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

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
        url = f"{self.API_URL}/getCourts.php"

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
        Fetch recent court decisions using SUDRF search.

        SUDRF has a complex AJAX API for searching decisions. This implementation
        provides a basic framework that can be extended with specific API parameters.

        Reference: https://github.com/tochno-st/sudrfscraper

        Args:
            since: Start date for decisions
            limit: Maximum number of decisions to fetch

        Returns:
            List of decision metadata
        """
        logger.info(f"Fetching SUDRF decisions since {since} (limit: {limit})")

        decisions = []
        session = await self._get_session()

        # SUDRF search URL - this is a simplified approach
        # In reality, SUDRF requires complex POST requests with specific parameters
        # This is a starting point that can be expanded based on actual API behavior

        try:
            # Try to fetch the main SUDRF search page
            search_url = f"{self.BASE_URL}/sf/"

            async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                response.raise_for_status()
                html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')

            # Look for decision links in the response
            # SUDRF typically uses patterns like /sf-{id}.html or /ms/{id}.html
            decision_links = soup.find_all("a", href=re.compile(r"(/sf-|/ms/|/gs/|/vs/).*\.html"))

            for link in decision_links[:limit]:
                try:
                    href = link.get("href", "")
                    if not href:
                        continue

                    # Build full URL
                    full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                    # Extract case ID from URL
                    case_id = self._extract_case_id(href)

                    # Extract case number from link text or nearby elements
                    case_number = link.get_text(strip=True)
                    if not case_number or len(case_number) < 5:
                        # Try to find case number in nearby elements
                        parent = link.find_parent("div") or link.find_parent("td")
                        if parent:
                            case_number = parent.get_text(strip=True)

                    decision_info = {
                        "case_id": case_id,
                        "case_number": case_number[:200] if case_number else f"Case-{case_id}",
                        "url": full_url,
                        "source": "sudrf",
                    }

                    # Avoid duplicates
                    if not any(d.get("case_id") == case_id for d in decisions):
                        decisions.append(decision_info)

                except Exception as e:
                    logger.debug(f"Error parsing SUDRF decision link: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Failed to fetch SUDRF decisions via main search: {e}")

        # If we didn't find decisions via main search, log this for future enhancement
        if not decisions:
            logger.info(
                "SUDRF requires complex AJAX API integration. "
                "This placeholder provides the structure for implementation. "
                "See https://github.com/tochno-st/sudrfscraper for reference implementation."
            )

        logger.info(f"Found {len(decisions)} SUDRF decisions")
        return decisions

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

    async def fetch_document(self, doc_id: str) -> RawDocument:
        """
        Fetch single court decision by ID.

        Args:
            doc_id: Case number or decision ID

        Returns:
            RawDocument with content and metadata
        """
        logger.info(f"Fetching court decision: {doc_id}")

        # Construct decision URL
        url = f"{self.BASE_URL}/sf-{doc_id}.html"

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
