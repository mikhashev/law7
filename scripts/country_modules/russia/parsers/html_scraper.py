"""
HTML Scraper for Detailed Amendment Text from pravo.gov.ru.

This module fetches and parses the HTML pages of amendments to extract
detailed information about which articles are changed and what those changes are.

The pravo.gov.ru API only provides metadata (titles, names), but the HTML pages
contain the full amendment text with article-level details.

This is the Russia-specific scraper for the official Russian legal document portal.
"""
import logging
import re
import sys
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from core.config import PRAVO_API_TIMEOUT

logger = logging.getLogger(__name__)


class AmendmentHTMLScraper:
    """
    Scraper for detailed amendment text from pravo.gov.ru HTML pages (Russia).

    This is the Russia-specific scraper for fetching detailed amendment text.

    Fetches the HTML version of amendments and extracts:
    - Full amendment text (not just metadata)
    - Specific article changes
    - Old text -> new text mappings
    - Effective dates

    Attributes:
        country_id: ISO 3166-1 alpha-3 code ("RUS")
        country_name: Full country name ("Russia")
        country_code: ISO 3166-1 alpha-2 code ("RU")
    """

    # Country identification
    country_id = "RUS"
    country_name = "Russia"
    country_code = "RU"

    BASE_URL = "http://publication.pravo.gov.ru"

    def __init__(self, timeout: int = PRAVO_API_TIMEOUT):
        """
        Initialize the scraper.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Law7/0.1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        })

    def get_amendment_html(self, eo_number: str) -> Optional[str]:
        """
        Fetch the HTML content of an amendment.

        Args:
            eo_number: Amendment document number (e.g., '0001202512290020')

        Returns:
            HTML content as string, or None if failed
        """
        url = f"{self.BASE_URL}/Document/View/{eo_number}"

        try:
            logger.debug(f"Fetching HTML from: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch HTML for {eo_number}: {e}")
            return None

    def parse_amendment_html(
        self,
        eo_number: str,
        html: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse the HTML content of an amendment.

        Args:
            eo_number: Amendment document number
            html: HTML content (optional, will fetch if not provided)

        Returns:
            Dictionary with parsed amendment data:
                - full_text: Complete amendment text
                - articles_affected: List of article numbers
                - changes: List of change descriptions
                - effective_date: When amendment takes effect
        """
        if html is None:
            html = self.get_amendment_html(eo_number)
            if not html:
                return {
                    'eo_number': eo_number,
                    'full_text': '',
                    'articles_affected': [],
                    'changes': [],
                    'error': 'Failed to fetch HTML',
                }

        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()

        # Extract main text content
        main_content = soup.find('div', class_='card') or soup.find('main') or soup.find('body')
        if not main_content:
            main_content = soup

        # Get text while preserving some structure
        full_text = self._extract_text(main_content)

        # Clean technical metadata (keep only valuable legal content)
        full_text = self._clean_technical_metadata(full_text)

        # Extract article references
        articles_affected = self._extract_article_references(full_text)

        # Extract specific changes
        changes = self._extract_changes(full_text)

        # Extract effective date
        effective_date = self._extract_effective_date(full_text, eo_number)

        return {
            'eo_number': eo_number,
            'full_text': full_text,
            'articles_affected': articles_affected,
            'changes': changes,
            'effective_date': effective_date,
        }

    def _extract_text(self, element) -> str:
        """
        Extract text from an element while preserving some structure.

        Args:
            element: BeautifulSoup element

        Returns:
            Extracted text with reasonable formatting
        """
        seen = set()  # Track elements we've already processed

        texts = []
        for child in element.descendants:
            # Skip if we've already processed this exact element
            element_id = id(child)
            if element_id in seen:
                continue
            seen.add(element_id)

            if child.name in ['p', 'br']:
                texts.append('\n')
            elif child.name in ['li', 'tr']:
                texts.append('\n- ')
            elif child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title']:
                # Skip titles as they're usually duplicates
                continue
            elif child.name and child.string and child.string.strip():
                text = child.string.strip()
                if text and texts and texts[-1][-1:] not in ['\n', ' ']:
                    texts.append(' ')
                texts.append(text)

        return ' '.join(''.join(texts).split()).strip()

    def _extract_article_references(self, text: str) -> List[str]:
        """
        Extract article numbers from amendment text.

        Args:
            text: Amendment text

        Returns:
            List of article numbers found
        """
        articles = []

        # Pattern for article references
        patterns = [
            r'стать(?:и|ью|е|я) (\d+(?:[\.\-]\d+)*)',  # статья 123, статьи 123-456
            r'ст\. (\d+(?:[\.\-]\d+)*)',  # ст. 123
            r'пункт (\d+)',  # пункт 123
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            articles.extend(matches)

        # Deduplicate while preserving order
        seen = set()
        unique_articles = []
        for article in articles:
            if article not in seen:
                seen.add(article)
                unique_articles.append(article)

        return unique_articles

    def _extract_changes(self, text: str) -> List[Dict[str, str]]:
        """
        Extract specific changes from amendment text.

        Args:
            text: Amendment text

        Returns:
            List of change dictionaries with keys:
                - type: 'replacement', 'addition', 'repeal'
                - article: article number if applicable
                - old_text: text being replaced/removed
                - new_text: replacement/new text
        """
        changes = []

        # Pattern: "слово X заменить словом Y"
        replacement_pattern = r'(?:слово|фразу|абзац|пункт)\s+["«]([^"»]+)["»]\s+заменить\s+["«]([^"»]+)["»]'
        for match in re.finditer(replacement_pattern, text, re.IGNORECASE):
            changes.append({
                'type': 'replacement',
                'old_text': match.group(1),
                'new_text': match.group(2),
                'context': match.group(0),
            })

        # Pattern: "Дополнить статьей X: Y"
        addition_pattern = r'Дополнить\s+стать(?:е|ей|ю|ей)\s+(\d+).*?[:]\s*([^.\n]+)'
        for match in re.finditer(addition_pattern, text, re.IGNORECASE):
            changes.append({
                'type': 'addition',
                'article': match.group(1),
                'new_text': match.group(2).strip(),
                'context': match.group(0),
            })

        # Pattern: "Признать утратившим силу статью X"
        repeal_pattern = r'Признать\s+утратившим\s+силу\s+стать(?:я|ю|и)\s+(\d+)'
        for match in re.finditer(repeal_pattern, text, re.IGNORECASE):
            changes.append({
                'type': 'repeal',
                'article': match.group(1),
                'context': match.group(0),
            })

        logger.debug(f"Extracted {len(changes)} changes from amendment text")
        return changes

    def _extract_effective_date(
        self,
        text: str,
        eo_number: str,
    ) -> Optional[str]:
        """
        Extract effective date from amendment text.

        Args:
            text: Amendment text
            eo_number: Document number (may contain date)

        Returns:
            Date string in YYYY-MM-DD format, or None
        """
        # Try to extract from text first
        date_patterns = [
            r'Федеральный\s+закон\s+от\s+(\d+)\.(\d+)\.(\d{4})',  # Федеральный закон от DD.MM.YYYY
            r'Дата\s+опубликования:\s*(\d+)\.(\d+)\.(\d{4})',  # Дата опубликования: DD.MM.YYYY
            r'с\s+(\d+)\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})\s+года',
        ]

        for date_pattern in date_patterns:
            date_match = re.search(date_pattern, text)
            if date_match:
                day, month, year = date_match.groups()
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        return None

    def _clean_technical_metadata(self, text: str) -> str:
        """
        Remove technical metadata from scraped text.

        Filters out non-legal content like publication numbers, dates,
        page numbers, and navigation elements.

        Args:
            text: Raw scraped text

        Returns:
            Cleaned text with only valuable legal content
        """
        # Patterns to remove (technical metadata)
        patterns_to_remove = [
            r'Номер опубликования:\s*\d+',
            r'Дата опубликования:\s*[\d.]+',
            r'Страница\s+\d+\s+из\s+\d+',
        ]

        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Clean up extra whitespace
        return ' '.join(text.split()).strip()

    def scrape_amendment_batch(
        self,
        eo_numbers: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple amendments in batch.

        Args:
            eo_numbers: List of amendment document numbers

        Returns:
            List of parsed amendment dictionaries
        """
        results = []

        for eo_number in eo_numbers:
            try:
                result = self.parse_amendment_html(eo_number)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to scrape {eo_number}: {e}")
                results.append({
                    'eo_number': eo_number,
                    'full_text': '',
                    'articles_affected': [],
                    'changes': [],
                    'error': str(e),
                })

        logger.info(f"Scraped {len(results)}/{len(eo_numbers)} amendments")
        return results

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def scrape_amendment(eo_number: str) -> Dict[str, Any]:
    """
    Convenience function to scrape a single amendment.

    Args:
        eo_number: Amendment document number

    Returns:
        Parsed amendment dictionary

    Example:
        >>> from country_modules.russia.parsers.html_scraper import scrape_amendment
        >>> result = scrape_amendment('0001202512290020')
        >>> print(result['full_text'][:200])
    """
    with AmendmentHTMLScraper() as scraper:
        return scraper.parse_amendment_html(eo_number)


# Test function
def test_html_scraper():
    """Test the HTML scraper with a sample amendment."""
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    with AmendmentHTMLScraper() as scraper:
        # Use a recent amendment from the database
        result = scraper.parse_amendment_html('0001202512290020')

        logger.info(f"EO Number: {result['eo_number']}")
        logger.info(f"Full Text Length: {len(result['full_text'])} chars")
        logger.info(f"Articles Affected: {result['articles_affected']}")
        logger.info(f"Changes Extracted: {len(result['changes'])}")
        logger.info(f"Effective Date: {result['effective_date']}")

        if result['full_text']:
            logger.debug(f"First 500 chars: {result['full_text'][:500]}...")

        if result['changes']:
            change_count = len(result['changes'])
            logger.info(f"Changes: {change_count}")
            for change in result['changes'][:5]:  # Show first 5
                logger.info(f"  - {change['type']}: {change.get('article', 'N/A')}")

        return result


if __name__ == "__main__":
    test_html_scraper()
