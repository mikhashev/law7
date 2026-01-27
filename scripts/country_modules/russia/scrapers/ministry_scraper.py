"""
Ministry interpretation scraper for Russian government agencies.

This module handles scraping of official ministry letters and interpretations.
Phase 7C focuses on:
- Ministry of Finance (Минфин) - tax law interpretations
- Federal Tax Service (ФНС) - tax procedure clarifications
- Rostrud - labor law interpretations

Sources:
- Minfin: https://minfin.gov.ru/ru/document/
- FNS: https://www.nalog.gov.ru/rn77/about_fts/docs/
- Rostrud: https://rostrud.gov.ru/legal/letters/
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, timedelta
from dataclasses import dataclass
import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup

from ...base.scraper import BaseScraper, RawDocument
from ....core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MinistryLetter:
    """Ministry letter / interpretation data structure."""

    agency_id: str  # UUID from government_agencies table
    agency_name_short: str  # e.g., "Минфин", "ФНС", "Роструд"
    document_type: str  # 'letter', 'guidance', 'instruction', 'explanation'
    document_number: str
    document_date: date
    title: Optional[str] = None
    question: Optional[str] = None  # The question being answered
    answer: Optional[str] = None  # The official answer
    full_content: Optional[str] = None
    legal_topic: Optional[str] = None
    related_laws: Optional[Dict[str, List[str]]] = None
    binding_nature: str = "informational"  # 'official', 'informational', 'recommendation'
    source_url: Optional[str] = None


# Agency configuration for Phase 7C
PHASE7C_AGENCIES: Dict[str, Dict[str, Any]] = {
    "minfin": {
        "agency_name_short": "Минфин",
        "agency_name": "Министерство финансов Российской Федерации",
        "agency_type": "ministry",
        "base_url": "https://minfin.gov.ru",
        "letters_url": "https://minfin.gov.ru/ru/document/",
        "legal_topics": ["tax", "budget", "finance"],
    },
    "fns": {
        "agency_name_short": "ФНС",
        "agency_name": "Федеральная налоговая служба",
        "agency_type": "service",
        "base_url": "https://www.nalog.gov.ru",
        "letters_url": "https://www.nalog.gov.ru/rn77/about_fts/docs/",
        "legal_topics": ["tax_procedure", "tax_administration"],
    },
    "rostrud": {
        "agency_name_short": "Роструд",
        "agency_name": "Федеральная служба по труду и занятости",
        "agency_type": "service",
        "base_url": "https://rostrud.gov.ru",
        "letters_url": "https://rostrud.gov.ru/legal/letters/",
        "legal_topics": ["labor", "employment", "social_protection"],
    },
}


class MinistryScraper(BaseScraper):
    """
    Scraper for ministry official letters and interpretations.

    Phase 7C focuses on Minfin, FNS, and Rostrud.
    """

    def __init__(self, agency_key: str):
        """
        Initialize ministry scraper.

        Args:
            agency_key: Agency key from PHASE7C_AGENCIES
        """
        if agency_key not in PHASE7C_AGENCIES:
            raise ValueError(
                f"Unknown agency: {agency_key}. "
                f"Available: {list(PHASE7C_AGENCIES.keys())}"
            )

        self.agency_key = agency_key
        self.agency_config = PHASE7C_AGENCIES[agency_key]

        settings = get_settings()
        self.timeout = settings.http_timeout
        self.batch_size = settings.batch_size
        self.max_retries = 3
        self._session = None
        self._connector = None

    @property
    def country_id(self) -> str:
        return "RUS"

    @property
    def country_name(self) -> str:
        return "Russia"

    @property
    def country_code(self) -> str:
        return "RU"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._connector = aiohttp.TCPConnector(limit=10)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={"User-Agent": "Law7/0.1.0"}
            )
        return self._session

    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL with retry logic.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        session = await self._get_session()

        for attempt in range(self.max_retries):
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.text()
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Failed to fetch {url} (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} attempts: {e}")
                    raise

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self._connector = None

    async def fetch_manifest(self, since: Optional[date] = None) -> Dict[str, Any]:
        """
        Get list of ministry letters published since date.

        For Minfin, this fetches the document listing page and extracts
        document metadata from the HTML.

        Args:
            since: Only return letters published after this date.

        Returns:
            Dict with letter list and metadata
        """
        logger.info(
            f"Fetching {self.agency_config['agency_name_short']} "
            f"letters since {since}"
        )

        if self.agency_key != "minfin":
            logger.warning(
                f"{self.agency_config['agency_name_short']} "
                "manifest fetching not yet implemented"
            )
            return {
                "agency_key": self.agency_key,
                "agency_name_short": self.agency_config["agency_name_short"],
                "letters": [],
                "last_updated": date.today().isoformat(),
                "metadata": {
                    "base_url": self.agency_config["base_url"],
                    "letters_url": self.agency_config["letters_url"],
                    "since": since.isoformat() if since else None,
                }
            }

        # Fetch Minfin document listing page
        url = self.agency_config["letters_url"]
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # Find document cards
        # Based on test results, the structure is:
        # .main_page_container .document_list .document_card.inner_link
        letters = []

        # Look for document cards directly
        doc_cards = soup.find_all("div", class_="document_card")
        logger.info(f"Found {len(doc_cards)} document_card elements")

        for card in doc_cards:
            # Find the main link in the card
            link = card.find("a", class_="inner_link")
            if not link:
                link = card.find("a", href=True)

            if link and link.get("href"):
                href = link.get("href")
                text = link.get_text(strip=True)

                # Try to extract date and number from the card
                doc_date = None
                doc_number = None

                # Look for date in the card
                date_elem = card.find("div", class_="date_list")
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    doc_date = self._extract_date_from_text(date_text)

                # Look for document number in the card or link text
                doc_number = self._extract_number_from_text(text)
                if not doc_number:
                    doc_number = self._extract_number_from_text(card.get_text())

                letter_info = {
                    "url": f"{self.agency_config['base_url']}{href}" if href.startswith("/") else href,
                    "title": text[:200],  # Limit title length
                    "document_number": doc_number,
                    "document_date": doc_date.isoformat() if doc_date else None,
                }

                letters.append(letter_info)

        logger.info(f"Extracted {len(letters)} letter URLs from document cards")

        manifest = {
            "agency_key": self.agency_key,
            "agency_name_short": self.agency_config["agency_name_short"],
            "letters": letters[:self.batch_size],  # Limit to batch size
            "last_updated": date.today().isoformat(),
            "metadata": {
                "base_url": self.agency_config["base_url"],
                "letters_url": self.agency_config["letters_url"],
                "since": since.isoformat() if since else None,
                "total_found": len(letters),
            }
        }

        return manifest

    def _extract_date_from_text(self, text: str) -> Optional[date]:
        """Extract date from text (format: DD.MM.YYYY)."""
        # Match date pattern: DD.MM.YYYY
        match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if match:
            day, month, year = match.groups()
            try:
                return date(int(year), int(month), int(day))
            except ValueError:
                pass
        return None

    def _extract_number_from_text(self, text: str) -> Optional[str]:
        """Extract document number from text (format: XX-XX-XX/XXXXX)."""
        # Match number pattern: XX-XX-XX/XXXXX
        match = re.search(r"\d{2}-\d{2}-\d{2}/\d+", text)
        if match:
            return match.group(0)
        return None

    async def fetch_document(self, doc_id: str) -> RawDocument:
        """
        Fetch single ministry letter by ID.

        For Minfin, doc_id is the URL path to the document detail page.

        Args:
            doc_id: Document URL (full URL or path)

        Returns:
            RawDocument with content and metadata
        """
        if self.agency_key != "minfin":
            raise NotImplementedError(
                f"{self.agency_config['agency_name_short']} "
                "document fetching not yet implemented"
            )

        # Construct full URL if doc_id is a path
        if doc_id.startswith("http"):
            url = doc_id
        else:
            url = f"{self.agency_config['base_url']}{doc_id}"

        logger.info(f"Fetching document from {url}")

        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract document content
        content_div = soup.find("div", class_=re.compile(r"content|text|document|doc-body"))
        if not content_div:
            # Try other common selectors
            content_div = soup.find("article") or soup.find("main")

        # Extract text content
        full_text = ""
        if content_div:
            # Get all paragraphs
            paragraphs = content_div.find_all("p")
            full_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        # Extract metadata
        title_elem = soup.find("h1") or soup.find("h2", class_=re.compile(r"title"))
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Try to extract date and number from title or content
        doc_date = self._extract_date_from_text(title)
        if not doc_date:
            doc_date = self._extract_date_from_text(full_text)

        doc_number = self._extract_number_from_text(title)
        if not doc_number:
            doc_number = self._extract_number_from_text(full_text)

        metadata = {
            "agency_key": self.agency_key,
            "agency_name_short": self.agency_config["agency_name_short"],
            "title": title,
            "document_number": doc_number,
            "document_date": doc_date.isoformat() if doc_date else None,
            "source_url": url,
        }

        return RawDocument(
            doc_id=doc_id,
            url=url,
            content=full_text.encode("utf-8"),
            content_type="text/html",
            metadata=metadata
        )

    async def fetch_updates(self, since: date) -> List[RawDocument]:
        """
        Fetch all ministry letters published since date.

        For Minfin, this fetches the manifest and then retrieves each document.

        Args:
            since: Start date for updates

        Returns:
            List of RawDocument objects
        """
        logger.info(
            f"Fetching {self.agency_config['agency_name_short']} "
            f"updates since {since}"
        )

        if self.agency_key != "minfin":
            logger.warning(
                f"{self.agency_config['agency_name_short']} "
                "updates fetching not yet implemented"
            )
            return []

        # Fetch manifest (list of documents)
        manifest = await self.fetch_manifest(since=since)

        # Fetch each document
        documents = []
        for letter_info in manifest["letters"]:
            try:
                doc = await self.fetch_document(letter_info["url"])
                documents.append(doc)
            except Exception as e:
                logger.error(f"Failed to fetch document {letter_info.get('url')}: {e}")
                continue

        logger.info(f"Fetched {len(documents)} documents since {since}")
        return documents

    async def verify_document(self, doc_id: str, content_hash: str) -> bool:
        """
        Verify ministry letter content matches hash.

        Args:
            doc_id: Document identifier
            content_hash: Expected hash value (SHA-256)

        Returns:
            bool: True if hash matches
        """
        doc = await self.fetch_document(doc_id)
        computed_hash = hashlib.sha256(doc.content).hexdigest()
        return computed_hash == content_hash

    async def fetch_letters(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        legal_topic: Optional[str] = None
    ) -> List[MinistryLetter]:
        """
        Fetch ministry letters for a date range and topic.

        For Minfin, this fetches documents using fetch_updates and
        converts them to MinistryLetter objects.

        Args:
            start_date: Start date for letters (default: 5 years ago)
            end_date: End date for letters (default: today)
            legal_topic: Filter by legal topic (not yet implemented for Minfin)

        Returns:
            List of ministry letters
        """
        if not start_date:
            # Phase 7C: last 5 years
            start_date = date.today() - timedelta(days=5 * 365)
        if not end_date:
            end_date = date.today()

        logger.info(
            f"Fetching {self.agency_config['agency_name_short']} letters "
            f"from {start_date} to {end_date}"
            + (f" for topic: {legal_topic}" if legal_topic else "")
        )

        if self.agency_key != "minfin":
            logger.warning(
                f"{self.agency_config['agency_name_short']} "
                "letters fetching not yet implemented"
            )
            return []

        # Fetch documents as RawDocument
        raw_docs = await self.fetch_updates(since=start_date)

        # Convert to MinistryLetter objects
        letters = []
        for doc in raw_docs:
            # Extract question/answer structure if present
            content = doc.content.decode("utf-8", errors="ignore")

            # Try to identify Q&A pattern
            question, answer = self._extract_question_answer(content)

            # Extract document date from metadata or content
            doc_date = None
            if doc.metadata.get("document_date"):
                try:
                    doc_date = date.fromisoformat(doc.metadata["document_date"])
                except ValueError:
                    pass

            letter = MinistryLetter(
                agency_id="",  # Will be filled by import script
                agency_name_short=self.agency_config["agency_name_short"],
                document_type="letter",
                document_number=doc.metadata.get("document_number", ""),
                document_date=doc_date or date.today(),
                title=doc.metadata.get("title", ""),
                question=question,
                answer=answer,
                full_content=content,
                legal_topic=legal_topic,
                binding_nature="informational",
                source_url=doc.url
            )
            letters.append(letter)

        logger.info(f"Fetched {len(letters)} letters")
        return letters

    def _extract_question_answer(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Try to extract question/answer structure from document content.

        Many ministry letters follow a Q&A format. This attempts to identify it.

        Args:
            content: Document text content

        Returns:
            Tuple of (question, answer) or (None, None)
        """
        # Look for common Q&A patterns
        qa_patterns = [
            r"(?:Вопрос|Question):?\s*(.+?)(?:\n|$)(?:Ответ|Answer):?\s*(.+)",
            r"(?:Q|Вопрос):?\s*(.+?)(?:\n|$)(?:A|Ответ):?\s*(.+)",
        ]

        for pattern in qa_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                question = match.group(1).strip()
                answer = match.group(2).strip()
                # Limit length
                if len(question) > 500:
                    question = question[:500] + "..."
                if len(answer) > 5000:
                    answer = answer[:5000] + "..."
                return question, answer

        return None, None

    async def fetch_recent_letters(
        self,
        years: int = 5,
        limit: Optional[int] = None
    ) -> List[MinistryLetter]:
        """
        Fetch recent ministry letters from the last N years.

        Args:
            years: Number of years back to fetch (Phase 7C: 5 years)
            limit: Maximum number of letters to fetch

        Returns:
            List of ministry letters
        """
        start_date = date.today() - timedelta(days=years * 365)
        letters = await self.fetch_letters(start_date=start_date)

        if limit:
            letters = letters[:limit]

        return letters


def get_agency_config(agency_key: str) -> Dict[str, Any]:
    """
    Get configuration for a specific agency.

    Args:
        agency_key: Agency key from PHASE7C_AGENCIES

    Returns:
        Agency configuration dict
    """
    if agency_key not in PHASE7C_AGENCIES:
        raise ValueError(
            f"Unknown agency: {agency_key}. "
            f"Available: {list(PHASE7C_AGENCIES.keys())}"
        )
    return PHASE7C_AGENCIES[agency_key]


def list_phase7c_agencies() -> List[str]:
    """
    Get list of Phase 7C target agency keys.

    Returns:
        List of agency keys for target ministries
    """
    return list(PHASE7C_AGENCIES.keys())


async def fetch_all_phase7c_letters(
    years: int = 5
) -> Dict[str, List[MinistryLetter]]:
    """
    Fetch letters from all Phase 7C target agencies.

    Args:
        years: Number of years back to fetch (Phase 7C: 5 years)

    Returns:
        Dict mapping agency_key to list of letters
    """
    logger.info(f"Fetching letters from all Phase 7C agencies (last {years} years)")

    all_letters = {}

    for agency_key in list_phase7c_agencies():
        try:
            scraper = MinistryScraper(agency_key)
            letters = await scraper.fetch_recent_letters(years=years)
            all_letters[agency_key] = letters
            logger.info(f"Fetched {len(letters)} letters from {agency_key}")
        except Exception as e:
            logger.error(f"Failed to fetch letters from {agency_key}: {e}")
            all_letters[agency_key] = []

    return all_letters
