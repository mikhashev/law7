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

from scripts.country_modules.base.scraper import BaseScraper, RawDocument
from scripts.core.config import get_settings

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
        "letters_url": "https://minfin.gov.ru/ru/perfomance/tax_relations/Answers/",
        "documents_url": "https://minfin.gov.ru/ru/document/",
        "legal_topics": ["tax", "budget", "finance"],
        "pagination_param": "page_4",  # Minfin general documents use ?page_4=2
        "ajax_pagination_param": "page_57",  # Minfin Answers use AJAX ?page_57=2
        "answers_topics": [
            "commonlaw",      # Общие вопросы
            "orgprofit",      # Прибыль организаций
            "fizprofit",      # НДФЛ
            "property",       # Имущественные налоги
            "indirect",       # Косвенные налоги (НДС, акцизы)
            "international",  # Международные налоги
            "special",        # Специальные налоговые режимы
            "transfert",      # Transfer pricing
            "foreign",        # Налоги за пределами РФ
            "customs_value",  # Таможенная стоимость
            "imposition",     # Обложение природных ресурсов
        ],
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

    async def fetch_manifest(
        self,
        since: Optional[date] = None,
        limit: Optional[int] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get list of ministry letters published since date.

        For Minfin, this can fetch from:
        - Answers section (Q&A content, default)
        - General Documents section (PDF/DOCX files)

        For FNS, this uses the search API with Actual-only filter.

        Args:
            since: Only return letters published after this date.
            limit: Maximum number of letters to fetch (if None, fetch all).
            source: For Minfin: "answers" (default) or "general_documents"

        Returns:
            Dict with letter list and metadata
        """
        logger.info(
            f"Fetching {self.agency_config['agency_name_short']} "
            f"letters since {since}" + (f" (limit: {limit})" if limit else "")
            + (f" (source: {source})" if source else "")
        )

        # FNS: Use search API
        if self.agency_key == "fns":
            return await self._fetch_fns_manifest(since, limit)

        # Minfin: Use Answers or General Documents
        if self.agency_key == "minfin":
            if source == "general_documents":
                return await self._fetch_minfin_general_documents(since, limit)
            else:
                return await self._fetch_minfin_manifest(since, limit)

        # Fallback for non-implemented agencies
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

    async def _fetch_fns_manifest(
        self,
        since: Optional[date] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch FNS document manifest from nalog.gov.ru using the search API.

        The FNS portal has a search API that filters by status and date:
        - st=0: Actual only (Актуально)
        - st=-1: All statuses
        - st=1: Not actual (Не актуально)

        Search API URL: https://www.nalog.gov.ru/rn77/about_fts/about_nalog/2.html?
                        n=&fd=&td=&fdp={from_date}&tdp={to_date}&ds=0&st=0&dn=0

        This method uses st=0 to fetch only actual documents directly.
        When 'since' is None, no date filter is applied (fdp=&tdp=).

        Args:
            since: Only return letters published after this date (if None, no date filter)
            limit: Maximum number of letters to fetch (if None, fetch all)

        Returns:
            Dict with letter list and metadata
        """
        logger.info(f"Fetching FNS manifest since {since} (Actual only via search API)")

        letters = []

        # Calculate date range for the search API
        # If 'since' is provided, use it as start date; otherwise leave empty (all dates)
        if since:
            from_date = since.strftime("%d.%m.%Y")
            to_date = date.today().strftime("%d.%m.%Y")
        else:
            # No date filter - fetch all Actual documents
            from_date = ""
            to_date = ""

        # Build search API URL with st=0 (Actual only)
        # URL pattern: https://www.nalog.gov.ru/rn77/about_fts/about_nalog/2.html?
        #             n=&fd=&td=&fdp={from}&tdp={to}&ds=0&st=0&dn=0
        search_url = (
            f"{self.agency_config['base_url']}/rn77/about_fts/about_nalog/1.html"
            f"?n=&fd=&td=&fdp={from_date}&tdp={to_date}&ds=0&st=0&dn=0"
        )

        logger.info(f"FNS Search URL: {search_url}")

        # Fetch the search results page
        html = await self._fetch_html(search_url)
        soup = BeautifulSoup(html, "html.parser")

        # Check for pagination in the search results
        # The FNS pagination shows pages like: 1 ... 103 104 105 106 [107]
        # We need to find the highest page number from all pagination links
        total_pages = 1
        # Look for pagination links - they may or may not have query params
        pagination_links = soup.find_all("a", href=re.compile(r"/about_nalog/\d+\.html"))
        if pagination_links:
            # Extract page numbers from pagination links
            page_numbers = []
            for link in pagination_links:
                href = link.get("href", "")
                # Look for page number in URL: /about_nalog/{page}.html
                match = re.search(r"/about_nalog/(\d+)\.html", href)
                if match:
                    page_numbers.append(int(match.group(1)))
            if page_numbers:
                total_pages = max(page_numbers)

        # Also check for the active page number (class="active" or class="pagination__show")
        # This handles cases where only the first page shows low numbers, but we need the last
        # The active page is marked with class="active"
        active_page = soup.find("a", class_="active")
        if active_page:
            active_text = active_page.get_text(strip=True)
            if active_text.isdigit():
                active_num = int(active_text)
                if active_num > total_pages:
                    total_pages = active_num

        logger.info(f"FNS search has {total_pages} pages of results")

        # Iterate through all pages of search results
        for page_num in range(1, total_pages + 1):
            # Construct page URL - use the pattern /about_nalog/{page}.html?{params}
            # Page 1: /about_nalog/1.html?params...
            # Page 2: /about_nalog/2.html?params...
            if page_num == 1:
                page_url = search_url
            else:
                # Replace the page number in the path: /about_nalog/1.html -> /about_nalog/{page_num}.html
                # Keep all query parameters the same
                params = search_url.split("?")[1] if "?" in search_url else ""
                page_url = f"{self.agency_config['base_url']}/rn77/about_fts/about_nalog/{page_num}.html?{params}"

            logger.info(f"Fetching FNS search page {page_num}/{total_pages}")

            # Fetch page HTML
            html = await self._fetch_html(page_url)
            soup = BeautifulSoup(html, "html.parser")

            # Debug: log HTML length
            logger.debug(f"Page HTML length: {len(html)} chars")

            # FNS search results are typically in a table or list
            # Look for document links - they use pattern: /rn77/about_fts/about_nalog/{ID}/
            doc_links = soup.find_all("a", href=re.compile(r"/rn77/about_fts/about_nalog/\d+/"))
            logger.debug(f"Found {len(doc_links)} document links on page {page_num}")

            page_letter_count = 0
            for link in doc_links:
                # Check limit before processing each document
                if limit and len(letters) >= limit:
                    break

                try:
                    # Get URL
                    href = link.get("href", "")
                    full_url = f"{self.agency_config['base_url']}{href}"

                    # Skip if already processed
                    if any(l["url"] == full_url for l in letters):
                        continue

                    # Extract text content
                    text = link.get_text(strip=True)

                    # Parse FNS format: "Письмо от 27 октября 2025 № БС-4-21/9645@"
                    doc_date = self._extract_fns_date_from_text(text)
                    doc_number = self._extract_fns_number_from_text(text)

                    # For FNS search results, the document number is often not in the link text
                    # Extract ID from URL as fallback: /rn77/about_fts/about_nalog/{ID}/
                    if not doc_number:
                        match = re.search(r"/about_nalog/(\d+)/", href)
                        if match:
                            doc_number = f"FNS-{match.group(1)}"  # Use ID as temporary identifier
                        else:
                            logger.debug(f"Skipping document without number or ID: {text[:50]}")
                            continue

                    # Extract title (everything after the number)
                    title_parts = text.split("№")
                    if len(title_parts) > 1:
                        title = title_parts[1].strip()
                    else:
                        title = text

                    letter_info = {
                        "url": full_url,
                        "title": title[:200],
                        "document_number": doc_number,
                        "document_date": doc_date.isoformat() if doc_date else None,
                        "is_actual": True,  # All results from st=0 are actual
                    }

                    letters.append(letter_info)
                    page_letter_count += 1

                except Exception as e:
                    logger.debug(f"Error parsing FNS document link: {e}")
                    continue

            logger.info(f"Page {page_num}: found {page_letter_count} letters (total: {len(letters)})")

            # Stop if we reached the limit (if specified)
            if limit and len(letters) >= limit:
                logger.info(f"Reached limit of {limit} documents, stopping pagination")
                break

            # Add delay between pages to be polite to the server
            if page_num < total_pages:
                await asyncio.sleep(10)

        logger.info(f"Extracted {len(letters)} FNS letter URLs from {page_num} pages (Actual only)")

        return {
            "agency_key": self.agency_key,
            "agency_name_short": self.agency_config["agency_name_short"],
            "letters": letters,
            "last_updated": date.today().isoformat(),
            "metadata": {
                "base_url": self.agency_config["base_url"],
                "letters_url": self.agency_config["letters_url"],
                "since": since.isoformat() if since else None,
                "total_found": len(letters),
                "filter_actual_only": True,
            }
        }

    async def _fetch_minfin_manifest(
        self,
        since: Optional[date] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch Minfin document manifest from Answers section.

        Minfin Answers section has 11 topics, each IS a document page with Q&A content.
        Some topics have AJAX pagination using ?page_57=2 pattern.

        - URL: https://minfin.gov.ru/ru/perfomance/tax_relations/Answers/{topic}/
        - Topics: commonlaw, orgprofit, fizprofit, property, indirect,
                  international, special, transfert, foreign, customs_value, imposition

        Topics with pagination (2 pages each):
        - orgprofit, fizprofit, indirect, international, special, transfert, imposition

        Topics without pagination (single page):
        - commonlaw, property, foreign, customs_value

        Each page contains Q&A content that will be fetched by fetch_document().

        Args:
            since: Only return letters published after this date
            limit: Maximum number of letters to fetch (if None, fetch all)

        Returns:
            Dict with letter list and metadata
        """
        logger.info(f"Fetching Minfin manifest since {since}" + (f" (limit: {limit})" if limit else ""))

        letters = []
        topics = self.agency_config.get("answers_topics", [])
        pagination_param = self.agency_config.get("ajax_pagination_param", "page_57")

        for topic in topics:
            # Check limit before processing each topic
            if limit and len(letters) >= limit:
                break

            topic_url = f"{self.agency_config['letters_url']}{topic}/"

            # Fetch the topic page to check for pagination
            try:
                html = await self._fetch_html(topic_url)
                soup = BeautifulSoup(html, "html.parser")

                # Look for pagination links with page_57 parameter
                pagination_links = soup.find_all("a", href=re.compile(rf"{pagination_param}=\d+"))

                if pagination_links:
                    # Extract page numbers from pagination links
                    page_numbers = set([1])  # Always include page 1
                    for link in pagination_links:
                        href = link.get("href", "")
                        match = re.search(rf"{pagination_param}=(\d+)", href)
                        if match:
                            page_numbers.add(int(match.group(1)))

                    # Create a letter entry for each page
                    for page_num in sorted(page_numbers):
                        # Check limit before adding each page
                        if limit and len(letters) >= limit:
                            break

                        if page_num == 1:
                            page_url = topic_url
                            page_suffix = ""
                        else:
                            page_url = f"{topic_url}?{pagination_param}={page_num}"
                            page_suffix = f" (page {page_num})"

                        letter_info = {
                            "url": page_url,
                            "title": f"Minfin Answers: {topic}{page_suffix}",
                            "document_number": f"MINFIN-{topic.upper()}-P{page_num}",
                            "document_date": None,
                            "source": "answers",
                            "topic": topic,
                            "page": page_num,
                        }
                        letters.append(letter_info)

                    logger.info(f"Topic '{topic}': found {len(page_numbers)} pages")
                else:
                    # No pagination, single page
                    letter_info = {
                        "url": topic_url,
                        "title": f"Minfin Answers: {topic}",
                        "document_number": f"MINFIN-{topic.upper()}",
                        "document_date": None,
                        "source": "answers",
                        "topic": topic,
                        "page": 1,
                    }
                    letters.append(letter_info)

            except Exception as e:
                logger.error(f"Error fetching topic '{topic}': {e}")
                # Add the base topic URL as fallback
                letter_info = {
                    "url": topic_url,
                    "title": f"Minfin Answers: {topic}",
                    "document_number": f"MINFIN-{topic.upper()}",
                    "document_date": None,
                    "source": "answers",
                    "topic": topic,
                    "page": 1,
                }
                letters.append(letter_info)

        logger.info(f"Found {len(letters)} Minfin Answer pages across {len(topics)} topics")

        return {
            "agency_key": self.agency_key,
            "agency_name_short": self.agency_config["agency_name_short"],
            "letters": letters,
            "last_updated": date.today().isoformat(),
            "metadata": {
                "base_url": self.agency_config["base_url"],
                "letters_url": self.agency_config["letters_url"],
                "since": since.isoformat() if since else None,
                "total_found": len(letters),
                "sources": ["answers"],
            }
        }

    async def _fetch_minfin_general_documents(
        self,
        since: Optional[date] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch Minfin General Documents manifest.

        The General Documents section contains ~30,000+ documents in multiple formats:
        - PDF, DOCX, DOC, XPS files
        - AJAX pagination using ?page_4=2 pattern
        - URL: https://minfin.gov.ru/ru/document/

        Documents are listed with:
        - Document ID (id_4 parameter)
        - Title
        - Date
        - Download links (PDF, DOCX)
        - File size

        Args:
            since: Only return documents published after this date
            limit: Maximum number of documents to fetch (if None, fetch all)

        Returns:
            Dict with document list and metadata
        """
        logger.info(f"Fetching Minfin General Documents since {since}" + (f" (limit: {limit})" if limit else ""))

        documents = []
        base_url = self.agency_config['documents_url']  # https://minfin.gov.ru/ru/document/
        pagination_param = self.agency_config.get('pagination_param', 'page_4')

        # Fetch pages until we run out of documents or hit the limit
        page_num = 1
        consecutive_empty_pages = 0  # Stop after 3 consecutive empty pages (safety measure)
        max_consecutive_empty = 3

        while consecutive_empty_pages < max_consecutive_empty:
            # Check limit before fetching each page
            if limit and len(documents) >= limit:
                logger.info(f"Reached limit of {limit} documents, stopping pagination")
                break

            # Construct page URL
            if page_num == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}?{pagination_param}={page_num}"

            logger.info(f"Fetching General Documents page {page_num}")

            try:
                html = await self._fetch_html(page_url)
                soup = BeautifulSoup(html, 'html.parser')

                # Look for document links with id_4 parameter
                doc_links = soup.find_all("a", href=re.compile(r"\?id_4=\d+"))

                if not doc_links:
                    logger.info(f"No more documents found on page {page_num}, stopping pagination")
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_consecutive_empty:
                        break
                    page_num += 1
                    continue

                page_doc_count = 0
                for link in doc_links:
                    # Check limit before processing each document
                    if limit and len(documents) >= limit:
                        break

                    try:
                        href = link.get("href", "")
                        text = link.get_text(strip=True)

                        # Extract document ID
                        match = re.search(r"id_4=(\d+)", href)
                        if not match:
                            continue

                        doc_id = match.group(1)

                        # Skip duplicates
                        if any(d.get("doc_id") == doc_id for d in documents):
                            continue

                        # Build full URL for document detail page
                        detail_url = f"{self.agency_config['base_url']}{href}" if href.startswith("/") else href

                        doc_info = {
                            "url": detail_url,
                            "doc_id": doc_id,
                            "title": text[:200],
                            "document_number": f"MINFIN-DOC-{doc_id}",
                            "document_date": None,
                            "source": "general_documents",
                        }
                        documents.append(doc_info)
                        page_doc_count += 1

                    except Exception as e:
                        logger.debug(f"Error parsing document link: {e}")
                        continue

                logger.info(f"Page {page_num}: found {page_doc_count} documents (total: {len(documents)})")

                # Reset empty page counter if we found documents
                if page_doc_count > 0:
                    consecutive_empty_pages = 0
                else:
                    consecutive_empty_pages += 1
                    logger.info(f"Empty page {page_num}, consecutive empty: {consecutive_empty_pages}/{max_consecutive_empty}")

                # Add delay between pages to be polite
                await asyncio.sleep(5)

                page_num += 1

            except Exception as e:
                logger.error(f"Error fetching page {page_num}: {e}")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    break
                page_num += 1

        logger.info(f"Found {len(documents)} Minfin General Documents")

        return {
            "agency_key": self.agency_key,
            "agency_name_short": self.agency_config["agency_name_short"],
            "letters": documents,  # Use same key for compatibility
            "last_updated": date.today().isoformat(),
            "metadata": {
                "base_url": self.agency_config['base_url'],
                "documents_url": base_url,
                "since": since.isoformat() if since else None,
                "total_found": len(documents),
                "sources": ["general_documents"],
            }
        }

    async def _fetch_minfin_answers_topics(
        self,
        since: Optional[date] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        DEPRECATED: This method is no longer used.
        Each Answers topic page IS a document, not a container of documents.
        """
        return []

    def _extract_fns_date_from_text(self, text: str) -> Optional[date]:
        """
        Extract date from FNS document text.

        FNS format: "Письмо от 27 октября 2025"
        Or: "Письмо от 27.10.2025"

        Args:
            text: Text to search

        Returns:
            Date or None
        """
        # Match "от 27 октября 2025" or "от 27.10.2025"
        match = re.search(r"от\s+(\d{1,2})\s+([а-яёА-ЯЁё]+)\s+(\d{4})", text)
        if match:
            day, month_name, year = match.groups()
            # Map Russian month names to numbers
            months = {
                "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
                "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
            }
            month = months.get(month_name.lower())
            if month:
                try:
                    return date(int(year), month, int(day))
                except ValueError:
                    pass

        # Try DD.MM.YYYY format
        match = re.search(r"от\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if match:
            day, month, year = match.groups()
            try:
                return date(int(year), int(month), int(day))
            except ValueError:
                pass

        return None

    def _extract_fns_number_from_text(self, text: str) -> Optional[str]:
        """
        Extract FNS document number from text.

        FNS documents have format like:
        - "№ БС-4-21/9645@"
        - "№ БС-4-21/9645@"

        Args:
            text: Text to search

        Returns:
            Document number or None
        """
        # Match FNS number pattern: № XX-XX-XX/XXXXX@
        match = re.search(r"№\s*([А-Яа-яЁёA-Za-z0-9\-/]+@?)", text)
        if match:
            return match.group(1).strip()
        return None

    def _check_fns_document_validity(self, url: str) -> Optional[bool]:
        """
        Check if FNS document is marked as "Actual" (Актуально).

        FNS documents have validity status indicators in their HTML:
        - "Актуально" = Actual/Valid
        - "Не актуально" = Not actual/Revoked

        This method checks the document page HTML for the validity status.

        Args:
            url: Document URL to check

        Returns:
            True if document is actual, False if not actual, None if status cannot be determined
        """
        # We need to fetch the document page to check its status
        # This is synchronous, so we'll do it during async manifest fetching
        return None  # Will be checked in async method below

    async def _check_fns_document_validity_async(self, url: str) -> Optional[bool]:
        """
        Async version of FNS document validity check.

        Fetches the document page and looks for validity status indicator.

        Args:
            url: Document URL to check

        Returns:
            True if document is actual, False if not actual, None if status cannot be determined
        """
        try:
            html = await self._fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")

            # Look for tooltip_content div with validity status
            # Pattern: <div id="ip-content-XXXXX-X" class="tooltip_content">Актуально</div>
            tooltip_divs = soup.find_all("div", class_="tooltip_content")

            for div in tooltip_divs:
                text = div.get_text(strip=True)
                if "Актуально" in text:
                    return True
                elif "Не актуально" in text or "не актуально" in text:
                    return False

            # If no tooltip found, try to find status in other elements
            # Look for elements with "actual" or "status" in class/id
            status_elements = soup.find_all(class_=re.compile(r"status|actual|valid", re.I))
            for elem in status_elements:
                text = elem.get_text(strip=True)
                if "Не актуально" in text or "не актуально" in text:
                    return False
                elif "Актуально" in text:
                    return True

            # Default: if we can't determine status, assume it's valid
            # (better to include potentially valid docs than exclude them)
            return None

        except Exception as e:
            logger.debug(f"Error checking FNS document validity for {url}: {e}")
            return None

    async def fetch_document(self, doc_id: str) -> RawDocument:
        """
        Fetch single ministry letter by ID.

        For Minfin and FNS, doc_id is the URL path to the document detail page.

        Args:
            doc_id: Document URL (full URL or path)

        Returns:
            RawDocument with content and metadata
        """
        # For FNS: implement FNS document fetching
        if self.agency_key == "fns":
            return await self._fetch_fns_document(doc_id)

        # For Minfin: existing implementation
        if self.agency_key == "minfin":
            return await self._fetch_minfin_document(doc_id)

        # For others: not implemented
        raise NotImplementedError(
            f"{self.agency_config['agency_name_short']} "
            "document fetching not yet implemented"
        )

    async def _fetch_minfin_document(self, doc_id: str) -> RawDocument:
        """
        Fetch Minfin document (supports Answers and General Documents).

        For Answers pages: Extracts Q&A content from HTML.
        For General Documents: Extracts PDF/DOCX download links and metadata.

        Args:
            doc_id: Document URL (full URL or path)

        Returns:
            RawDocument with content and metadata
        """
        # Construct full URL if doc_id is a path
        if doc_id.startswith("http"):
            url = doc_id
        else:
            url = f"{self.agency_config['base_url']}{doc_id}"

        logger.info(f"Fetching Minfin document from {url}")

        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # Check if this is a General Document (has id_4 parameter or download links)
        is_general_doc = (
            "id_4=" in url or
            soup.find("a", href=re.compile(r"\.(pdf|docx|doc)", re.I))
        )

        if is_general_doc:
            # This is a General Document - extract file download links
            return await self._fetch_minfin_general_document(url, soup)
        else:
            # This is an Answers page - extract Q&A content
            return await self._fetch_minfin_answers_document(url, soup)

    async def _fetch_minfin_general_document(self, url: str, soup: BeautifulSoup) -> RawDocument:
        """
        Fetch Minfin General Document with PDF/DOCX download links.

        Extracts:
        - Title
        - Document date
        - Download links (PDF, DOCX, DOC)
        - File sizes
        - Document ID

        Args:
            url: Document detail page URL
            soup: BeautifulSoup object of the page

        Returns:
            RawDocument with metadata and file URLs
        """
        # Extract title
        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Extract document ID from URL
        doc_id = None
        match = re.search(r"id_4=(\d+)", url)
        if match:
            doc_id = match.group(1)

        # Find all download links
        all_links = soup.find_all("a", href=True)
        download_links = {
            "pdf": [],
            "docx": [],
            "doc": [],
            "other": []
        }

        for link in all_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Build full URL
            full_url = f"{self.agency_config['base_url']}{href}" if href.startswith("/") else href

            if ".pdf" in href.lower() or "pdf" in text.lower():
                download_links["pdf"].append(full_url)
            elif ".docx" in href.lower() or "docx" in text.lower():
                download_links["docx"].append(full_url)
            elif ".doc" in href.lower() and ".docx" not in href.lower():
                download_links["doc"].append(full_url)
            elif "/upload/" in href:
                download_links["other"].append(full_url)

        # Extract date from page
        doc_date = self._extract_date_from_text(title)

        # Build full text with download information
        full_text = f"Title: {title}\n"
        if doc_id:
            full_text += f"Document ID: {doc_id}\n"
        if doc_date:
            full_text += f"Date: {doc_date.isoformat()}\n"
        full_text += f"URL: {url}\n"

        if download_links["pdf"]:
            full_text += f"\nPDF files ({len(download_links['pdf'])}):\n"
            for pdf_url in download_links["pdf"]:
                full_text += f"  - {pdf_url}\n"

        if download_links["docx"]:
            full_text += f"\nDOCX files ({len(download_links['docx'])}):\n"
            for docx_url in download_links["docx"]:
                full_text += f"  - {docx_url}\n"

        # Try to extract some description from the page
        content_div = soup.find("div", class_=re.compile(r"content|text|document", re.I))
        if content_div:
            paragraphs = content_div.find_all("p")
            if paragraphs:
                full_text += "\nDescription:\n"
                for p in paragraphs[:5]:  # First 5 paragraphs
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        full_text += f"{text}\n"

        metadata = {
            "agency_key": self.agency_key,
            "agency_name_short": self.agency_config["agency_name_short"],
            "title": title,
            "document_number": f"MINFIN-DOC-{doc_id}" if doc_id else "",
            "document_date": doc_date.isoformat() if doc_date else None,
            "source_url": url,
            "doc_id": doc_id,
            "download_urls": download_links,
            "source": "general_documents",
        }

        return RawDocument(
            doc_id=url,
            url=url,
            content=full_text.encode("utf-8"),
            content_type="text/html",
            metadata=metadata
        )

    async def _fetch_minfin_answers_document(self, url: str, soup: BeautifulSoup) -> RawDocument:
        """
        Fetch Minfin Answers document (Q&A content).

        Args:
            url: Document URL
            soup: BeautifulSoup object of the page

        Returns:
            RawDocument with Q&A content
        """
        # Extract document content
        content_div = soup.find("div", class_=re.compile(r"content|text|document|doc-body"))
        if not content_div:
            content_div = soup.find("article") or soup.find("main")

        # Extract text content
        full_text = ""
        if content_div:
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
            "source": "answers",
        }

        return RawDocument(
            doc_id=url,
            url=url,
            content=full_text.encode("utf-8"),
            content_type="text/html",
            metadata=metadata
        )

    async def _fetch_fns_document(self, doc_id: str) -> RawDocument:
        """
        Fetch FNS document by URL.

        Args:
            doc_id: Document URL

        Returns:
            RawDocument with content and metadata
        """
        if doc_id.startswith("http"):
            url = doc_id
        else:
            url = f"{self.agency_config['base_url']}{doc_id}"

        logger.info(f"Fetching FNS document from {url}")

        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract document content - FNS structure may vary
        # Try multiple selectors for content
        content_div = (
            soup.find("div", class_=re.compile(r"content|text|document|doc-body", re.I)) or
            soup.find("article") or
            soup.find("main") or
            soup.find("div", class_="item-page")
        )

        # Extract text content
        full_text = ""
        if content_div:
            paragraphs = content_div.find_all("p")
            full_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        # Extract metadata
        title_elem = soup.find("h1") or soup.find("h2", class_=re.compile(r"title", re.I))
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Try to extract date and number
        doc_date = self._extract_date_from_text(title or full_text)
        doc_number = self._extract_fns_number_from_text(title or full_text)

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

    async def fetch_updates(
        self,
        since: date,
        limit: Optional[int] = None
    ) -> List[RawDocument]:
        """
        Fetch all ministry letters published since date.

        For Minfin and FNS, this fetches the manifest and then retrieves each document.

        Args:
            since: Start date for updates
            limit: Maximum number of letters to fetch (if None, fetch all)

        Returns:
            List of RawDocument objects
        """
        logger.info(
            f"Fetching {self.agency_config['agency_name_short']} "
            f"updates since {since}" + (f" (limit: {limit})" if limit else "")
        )

        # Fetch manifest (list of documents)
        manifest = await self.fetch_manifest(since=since, limit=limit)

        # Fetch each document
        documents = []
        for i, letter_info in enumerate(manifest["letters"]):
            try:
                doc = await self.fetch_document(letter_info["url"])
                documents.append(doc)

                # Add small delay between documents to prevent rate limiting
                # Sleep every 50 documents to avoid excessive delays
                if (i + 1) % 50 == 0 and i < len(manifest["letters"]) - 1:
                    logger.info(f"Pausing after {i + 1} documents (rate limiting)")
                    await asyncio.sleep(10)
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
        legal_topic: Optional[str] = None,
        limit: Optional[int] = None,
        _use_default_dates: bool = True
    ) -> List[MinistryLetter]:
        """
        Fetch ministry letters for a date range and topic.

        For Minfin, this fetches documents using fetch_updates and
        converts them to MinistryLetter objects.

        Args:
            start_date: Start date for letters (None for all dates when _use_default_dates=False)
            end_date: End date for letters (default: today)
            legal_topic: Filter by legal topic (not yet implemented for Minfin)
            limit: Maximum number of letters to fetch (if None, fetch all)
            _use_default_dates: If True (default), use 5-year default when start_date=None

        Returns:
            List of ministry letters
        """
        # Only set default start_date when explicitly requested (_use_default_dates=True)
        # This allows start_date=None with _use_default_dates=False to mean "all dates"
        if _use_default_dates and start_date is None and end_date is None:
            # Phase 7C: last 5 years as default
            start_date = date.today() - timedelta(days=5 * 365)
            end_date = date.today()
        elif end_date is None:
            end_date = date.today()

        if start_date is None:
            logger.info(
                f"Fetching {self.agency_config['agency_name_short']} letters "
                f"(ALL dates)" + (f" (limit: {limit})" if limit else "")
                + (f" for topic: {legal_topic}" if legal_topic else "")
            )
        else:
            logger.info(
                f"Fetching {self.agency_config['agency_name_short']} letters "
                f"from {start_date} to {end_date}" + (f" (limit: {limit})" if limit else "")
                + (f" for topic: {legal_topic}" if legal_topic else "")
            )

        # Fetch documents as RawDocument (pass None for all dates, and limit)
        raw_docs = await self.fetch_updates(since=start_date, limit=limit)

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
        years: Optional[int] = 5,
        limit: Optional[int] = None,
        source: Optional[str] = None
    ) -> List[MinistryLetter]:
        """
        Fetch recent ministry letters from the last N years.

        Args:
            years: Number of years back to fetch (None for all dates, Phase 7C: 5 years)
            limit: Maximum number of letters to fetch
            source: For Minfin: "answers" (default), "general_documents", or None for default

        Returns:
            List of ministry letters
        """
        # If years is None, fetch all letters (no date filter)
        # Pass _use_default_dates=False to prevent setting 5-year default
        if years is None:
            letters = await self.fetch_letters(start_date=None, limit=limit, _use_default_dates=False)
        else:
            start_date = date.today() - timedelta(days=years * 365)
            letters = await self.fetch_letters(start_date=start_date, limit=limit)

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
    years: Optional[int] = 5,
    limit: Optional[int] = None,
    source: Optional[str] = None,
    agency: Optional[str] = None
) -> Dict[str, List[MinistryLetter]]:
    """
    Fetch letters from all Phase 7C target agencies.

    Args:
        years: Number of years back to fetch (None for all dates, Phase 7C: 5 years)
        limit: Maximum number of letters to fetch per agency
        source: For Minfin: "answers" (default), "general_documents", or "both"
        agency: Fetch from specific agency only ("minfin", "fns", or "rostrud")

    Returns:
        Dict mapping agency_key to list of letters
    """
    if years is None:
        logger.info("Fetching letters from all Phase 7C agencies (ALL dates)")
    else:
        logger.info(f"Fetching letters from all Phase 7C agencies (last {years} years)")
    if limit:
        logger.info(f"Limit: {limit} letters per agency")
    if source:
        logger.info(f"Minfin source: {source}")
    if agency:
        logger.info(f"Agency filter: {agency}")

    # Determine which agencies to fetch from
    if agency:
        agencies_to_fetch = [agency]
    else:
        agencies_to_fetch = list_phase7c_agencies()

    all_letters = {}

    for agency_key in agencies_to_fetch:
        scraper = None
        try:
            scraper = MinistryScraper(agency_key)

            # For Minfin with "both" source, fetch from Answers and General Documents separately
            if agency_key == "minfin" and source == "both":
                # Fetch Answers
                answers_manifest = await scraper.fetch_manifest(since=None, limit=limit, source="answers")
                answers_letters = await _manifest_to_letters(scraper, answers_manifest)
                all_letters[f"{agency_key}_answers"] = answers_letters
                logger.info(f"Fetched {len(answers_letters)} letters from {agency_key} (Answers)")

                # Fetch General Documents
                general_manifest = await scraper.fetch_manifest(since=None, limit=limit, source="general_documents")
                general_letters = await _manifest_to_letters(scraper, general_manifest)
                all_letters[f"{agency_key}_general"] = general_letters
                logger.info(f"Fetched {len(general_letters)} letters from {agency_key} (General Documents)")
            # For Minfin with specific source
            elif agency_key == "minfin" and source:
                if source == "general_documents":
                    source_param = "general_documents"
                else:
                    source_param = "answers"

                manifest = await scraper.fetch_manifest(since=None, limit=limit, source=source_param)
                letters = await _manifest_to_letters(scraper, manifest)
                all_letters[agency_key] = letters
                logger.info(f"Fetched {len(letters)} letters from {agency_key} ({source_param})")
            else:
                letters = await scraper.fetch_recent_letters(years=years, limit=limit)
                all_letters[agency_key] = letters
                logger.info(f"Fetched {len(letters)} letters from {agency_key}")
        except Exception as e:
            logger.error(f"Failed to fetch letters from {agency_key}: {e}")
            all_letters[agency_key] = []
        finally:
            if scraper:
                await scraper.close()

    return all_letters


async def _manifest_to_letters(
    scraper: MinistryScraper,
    manifest: Dict[str, Any]
) -> List[MinistryLetter]:
    """
    Convert manifest to MinistryLetter objects.

    Args:
        scraper: MinistryScraper instance
        manifest: Manifest from fetch_manifest()

    Returns:
        List of MinistryLetter objects
    """
    letters = []
    for letter_info in manifest.get("letters", []):
        # Create a basic MinistryLetter object
        letter = MinistryLetter(
            agency_id="",  # Will be filled by import script
            agency_name_short=manifest.get("agency_name_short", scraper.agency_config["agency_name_short"]),
            document_type="letter",
            document_number=letter_info.get("document_number", ""),
            document_date=date.today(),
            title=letter_info.get("title", ""),
            full_content="",  # Will be filled when fetching document
            binding_nature="informational",
            source_url=letter_info["url"]
        )
        letters.append(letter)
    return letters
