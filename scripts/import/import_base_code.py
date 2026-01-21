"""
Import Base Legal Codes from Official Sources

This script imports the original/base text of Russian legal codes from:
1. kremlin.ru (official presidential publication portal)
2. pravo.gov.ru (official publication portal)
3. government.ru (official government publication portal)

The imported base code text serves as the foundation for applying amendments
during the consolidation process.

Usage:
    python -m scripts.import.import_base_code --code TK_RF
    python -m scripts.import.import_base_code --code GK_RF
    python -m scripts.import.import_base_code --list

Configuration:
    IMPORT_REQUEST_DELAY: Delay between requests in seconds (default: 2)
    IMPORT_REQUEST_TIMEOUT: Request timeout in seconds (default: 30)
    Set in .env file or environment variables.
"""

import argparse
import logging
import re
import sys
import time
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

from scripts.core.db import get_db_connection
from scripts.core.config import config

logger = logging.getLogger(__name__)


# Code metadata for import
# Priority: kremlin (official) -> pravo (official) -> government (official)
# Removed: consultant (paid subscription - no longer used)
CODE_METADATA = {
    # Multi-part codes
    "GK_RF": {
        "name": "Гражданский кодекс",
        "multi_part": True,
        "parts": [
            {
                "code_id": "GK_RF",
                "part": "1",
                "eo_number": "51-ФЗ",
                "original_date": date(1994, 11, 30),
                "kremlin_bank": "7279",
                "pravo_nd": "102033239",
            },
            {
                "code_id": "GK_RF_2",
                "part": "2",
                "eo_number": "51-ФЗ",
                "original_date": date(1994, 11, 30),
                "kremlin_bank": "8804",
                "pravo_nd": "102039276",
            },
            {
                "code_id": "GK_RF_3",
                "part": "3",
                "eo_number": "51-ФЗ",
                "original_date": date(1994, 11, 30),
                "kremlin_bank": "17547",
                "pravo_nd": "102073578",
            },
            {
                "code_id": "GK_RF_4",
                "part": "4",
                "eo_number": "51-ФЗ",
                "original_date": date(1994, 11, 30),
                "kremlin_bank": "24743",
                "pravo_nd": "102110716",
            },
        ],
    },
    "NK_RF": {
        "name": "Налоговый кодекс",
        "multi_part": True,
        "parts": [
            {
                "code_id": "NK_RF",
                "part": "1",
                "eo_number": "146-ФЗ",
                "original_date": date(2000, 7, 31),
                "kremlin_bank": "12755",
                "pravo_nd": "102054722",
                "government_url": "http://government.ru/docs/all/96558/",
            },
            {
                "code_id": "NK_RF_2",
                "part": "2",
                "eo_number": "146-ФЗ",
                "original_date": date(2000, 7, 31),
                "kremlin_bank": "15925",
                "pravo_nd": "102067058",
                "government_url": "http://government.ru/docs/all/96947/",
            },
        ],
    },
    # Constitution (special case - different URL structure)
    "KONST_RF": {
        "name": "Конституция Российской Федерации",
        "eo_number": None,
        "original_date": date(1993, 12, 12),
        "kremlin_url": "http://kremlin.ru/acts/constitution/item",
        "pravo_nd": "102027595",
        "is_constitution": True,
    },
    # Single-part codes
    "TK_RF": {
        "name": "Трудовой кодекс",
        "eo_number": "197-ФЗ",
        "original_date": date(2001, 12, 30),
        "kremlin_bank": "17706",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/17706",
        "pravo_nd": "102074279",
    },
    "UK_RF": {
        "name": "Уголовный кодекс",
        "eo_number": "63-ФЗ",
        "original_date": date(1996, 5, 24),
        "kremlin_bank": "9555",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/9555",
        "pravo_nd": "102041891",
    },
    "KoAP_RF": {
        "name": "Кодекс Российской Федерации об административных правонарушениях",
        "eo_number": "195-ФЗ",
        "original_date": date(2001, 12, 30),
        "kremlin_bank": "17704",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/17704",
        "pravo_nd": "102074277",
        "government_url": "http://government.ru/docs/all/97204/",
    },
    "SK_RF": {
        "name": "Семейный кодекс",
        "eo_number": "223-ФЗ",
        "original_date": date(1995, 12, 29),
        "kremlin_bank": "8671",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/8671",
        "pravo_nd": "102038925",
    },
    "ZhK_RF": {
        "name": "Жилищный кодекс",
        "eo_number": "188-ФЗ",
        "original_date": date(2004, 12, 29),
        "kremlin_bank": "21918",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/21918",
        "pravo_nd": "102090645",
    },
    "ZK_RF": {
        "name": "Земельный кодекс",
        "eo_number": "136-ФЗ",
        "original_date": date(2001, 10, 25),
        "kremlin_bank": "17478",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/17478",
        "pravo_nd": "102073184",
        "government_url": "http://government.ru/docs/all/136-fz.html",
    },
    # Civil Procedure Code (available on kremlin.ru)
    "GPK_RF": {
        "name": "Гражданский процессуальный кодекс",
        "eo_number": "138-ФЗ",
        "original_date": date(2002, 11, 14),
        "kremlin_bank": "18837",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/18837",
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/138-fz.html",
    },
    "APK_RF": {
        "name": "Арбитражный процессуальный кодекс",
        "eo_number": "95-ФЗ",
        "original_date": date(2002, 7, 24),
        "kremlin_bank": "18937",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/18937",
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/97382/",
    },
    "UPK_RF": {
        "name": "Уголовно-процессуальный кодекс",
        "eo_number": "174-ФЗ",
        "original_date": date(2001, 12, 18),
        "kremlin_bank": "17643",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/17643",
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/97184/",
    },
    # Budget Code
    "BK_RF": {
        "name": "Бюджетный кодекс Российской Федерации",
        "eo_number": "145-ФЗ",
        "original_date": date(1998, 7, 31),
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/96557/",
    },
    # Urban Planning Code
    "GRK_RF": {
        "name": "Градостроительный кодекс Российской Федерации",
        "eo_number": "190-ФЗ",
        "original_date": date(2004, 12, 29),
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/97828/",
    },
    # Criminal Executive Code
    "UIK_RF": {
        "name": "Уголовно-исполнительный кодекс Российской Федерации",
        "eo_number": "1-ФЗ",
        "original_date": date(1997, 1, 8),
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/96249/",
    },
    # Air Code
    "VZK_RF": {
        "name": "Воздушный кодекс Российской Федерации",
        "eo_number": "60-ФЗ",
        "original_date": date(1997, 3, 19),
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/96308/",
    },
    # Water Code
    "VDK_RF": {
        "name": "Водный кодекс Российской Федерации",
        "eo_number": "74-ФЗ",
        "original_date": date(2006, 6, 3),
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/98126/",
    },
    # Forest Code
    "LK_RF": {
        "name": "Лесной кодекс Российской Федерации",
        "eo_number": "200-ФЗ",
        "original_date": date(2006, 12, 4),
        "pravo_nd": None,
        "government_url": "http://government.ru/docs/all/98250/",
    },
    # Administrative Procedure Code
    "KAS_RF": {
        "name": "Кодекс административного судопроизводства Российской Федерации",
        "eo_number": "21-ФЗ",
        "original_date": date(2015, 3, 8),
        "kremlin_bank": "39498",
        "kremlin_url": "http://www.kremlin.ru/acts/bank/39498",
        "pravo_nd": None,
        "government_url": None,
    },
}


# =============================================================================
# Article Number Validation - Hybrid Context + Range Based
# =============================================================================

# Known article ranges for fallback validation (from official sources)
KNOWN_ARTICLE_RANGES = {
    'KONST_RF': (1, 137),
    'GK_RF': (1, 453),
    'GK_RF_2': (454, 1109),
    'GK_RF_3': (1110, 1224),
    'GK_RF_4': (1225, 1551),
    'UK_RF': (1, 361),
    'TK_RF': (1, 424),
    'NK_RF': (1, 142),
    'NK_RF_2': (143, 432),
    'KoAP_RF': (1, 890),
    'SK_RF': (1, 170),
    'ZhK_RF': (1, 165),
    'ZK_RF': (1, 85),
    'APK_RF': (1, 418),
    'GPK_RF': (1, 494),
    'UPK_RF': (1, 553),
    'BK_RF': (1, 280),
    'GRK_RF': (1, 120),
    'UIK_RF': (1, 200),
    'VZK_RF': (1, 150),
    'VDK_RF': (1, 100),
    'LK_RF': (1, 120),
    'KAS_RF': (1, 350),
}


def parse_article_number_for_comparison(article_number: str) -> float:
    """
    Parse article number for range comparison.
    Extracts base number (before first dot) for multi-dot formats.

    This allows "20.1.2" to be compared against range [1, 890] using value 20.0.
    Python's float("20.1.2") raises ValueError, so we extract the base number.

    Args:
        article_number: Article number like "1", "20.3", "20.3.1", "20.3.1.2"

    Returns:
        Float value for range comparison (base number only)
    """
    # Extract base number (everything before first dot, or full number if no dots)
    base_number = article_number.split('.')[0]
    return float(base_number) if base_number.isdigit() else 0.0


def try_context_correction(
    article_number: str,
    prev_article: Optional[str],
    next_article: Optional[str]
) -> tuple[str, List[str]]:
    """
    Attempt to correct article number based on surrounding context.

    Context-based approach: If article "1201" appears between "120" and "121",
    it's likely "120.1" not "1201".

    Args:
        article_number: Raw article number from HTML (e.g., "1201")
        prev_article: Previous article number in sequence (e.g., "120")
        next_article: Next article number in sequence (e.g., "121")

    Returns:
        Tuple of (corrected_number, warnings)
    """
    warnings: List[str] = []

    # Need both neighbors for context validation
    if not prev_article or not next_article:
        return article_number, warnings

    # If article already has dot or hyphen, it's likely correct
    if '.' in article_number or '-' in article_number:
        return article_number, warnings

    # Check if article_number is a pure number
    if not article_number.isdigit():
        return article_number, warnings

    # Try to parse neighbor articles using the multi-dot parser
    try:
        prev_num = parse_article_number_for_comparison(prev_article)
        next_num = parse_article_number_for_comparison(next_article)
    except ValueError:
        # Neighbors have complex formatting, can't use context
        return article_number, warnings

    # If current article fits between neighbors, it's correct
    try:
        current_num = parse_article_number_for_comparison(article_number)
        if prev_num < current_num < next_num:
            return article_number, warnings
    except ValueError:
        pass

    # Try inserting a dot before the last digit (e.g., "1201" → "120.1")
    if len(article_number) > 1:
        corrected = f"{article_number[:-1]}.{article_number[-1]}"
        try:
            corrected_num = parse_article_number_for_comparison(corrected)
            if prev_num < corrected_num < next_num:
                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                return corrected, warnings
        except ValueError:
            pass

    # Try inserting a dot before the last 2 digits (e.g., "1256" → "12.56" or "125.6")
    if len(article_number) > 2:
        # Try "125.6"
        corrected = f"{article_number[:-1]}.{article_number[-1:]}"
        try:
            corrected_num = parse_article_number_for_comparison(corrected)
            if prev_num < corrected_num < next_num:
                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                return corrected, warnings
        except ValueError:
            pass

        # Try "12.56"
        corrected = f"{article_number[:-2]}.{article_number[-2:]}"
        try:
            corrected_num = parse_article_number_for_comparison(corrected)
            if prev_num < corrected_num < next_num:
                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                return corrected, warnings
        except ValueError:
            pass

    # Could not correct with context
    return article_number, warnings


def try_range_correction(article_number: str, code_id: str) -> tuple[str, List[str]]:
    """
    Attempt to correct article number using known article ranges.

    Fallback method when context is not available.

    Args:
        article_number: Raw article number from HTML
        code_id: Code identifier (e.g., 'TK_RF')

    Returns:
        Tuple of (corrected_number, warnings)
    """
    warnings: List[str] = []

    # If article number contains dots or hyphens, it's likely correct
    if '.' in article_number or '-' in article_number:
        return article_number, warnings

    # Check if it's a pure number
    if not article_number.isdigit():
        return article_number, warnings

    num = int(article_number)
    range_info = KNOWN_ARTICLE_RANGES.get(code_id)

    if not range_info:
        # Unknown code - can't validate
        return article_number, warnings

    min_article, max_article = range_info

    # If within valid range, it's correct
    if min_article <= num <= max_article:
        return article_number, warnings

    # Number is out of range - try to correct
    # Pattern: "1256" might be "125.6" if 1256 > max_article
    # Pattern: "2031" might be "20.3.1" (multi-level article)
    if num > max_article:
        # Try inserting TWO dots FIRST for multi-level articles (e.g., "2031" → "20.3.1")
        # Multi-level articles are more specific, so try them before single-dot corrections
        if len(article_number) >= 4:
            # Try "20.3.1" format for 4-digit numbers: "2031" → "20.3.1"
            # Skip if middle digit is "0" (e.g., "1201" → "12.0.1" is unlikely, prefer "120.1")
            if len(article_number) == 4 and article_number[-2] != '0':
                corrected = f"{article_number[:-2]}.{article_number[-2]}.{article_number[-1]}"
                corrected_num = parse_article_number_for_comparison(corrected)
                if min_article <= corrected_num <= max_article:
                    warnings.append(f"Range-corrected: '{article_number}' → '{corrected}' (valid range: {min_article}-{max_article})")
                    return corrected, warnings

            # Try "20.3.12" format for 5+ digit numbers: "20312" → "20.3.12"
            if len(article_number) >= 5:
                corrected = f"{article_number[:-3]}.{article_number[-3]}.{article_number[-2:]}"
                corrected_num = parse_article_number_for_comparison(corrected)
                if min_article <= corrected_num <= max_article:
                    warnings.append(f"Range-corrected: '{article_number}' → '{corrected}' (valid range: {min_article}-{max_article})")
                    return corrected, warnings

                # Try "20.31.2" format: "20312" → "20.31.2"
                corrected = f"{article_number[:-2]}.{article_number[-2:-1]}.{article_number[-1]}"
                corrected_num = parse_article_number_for_comparison(corrected)
                if min_article <= corrected_num <= max_article:
                    warnings.append(f"Range-corrected: '{article_number}' → '{corrected}' (valid range: {min_article}-{max_article})")
                    return corrected, warnings

        # Try inserting a dot before the last digit (e.g., "1201" → "120.1")
        if num > 10:  # Need at least 2 digits
            corrected = f"{article_number[:-1]}.{article_number[-1]}"
            corrected_num = parse_article_number_for_comparison(corrected)
            if min_article <= corrected_num <= max_article:
                warnings.append(f"Range-corrected: '{article_number}' → '{corrected}' (valid range: {min_article}-{max_article})")
                return corrected, warnings

        # Try inserting a dot before the last 2 digits (e.g., "1256" → "12.56")
        if num > 100:
            corrected = f"{article_number[:-2]}.{article_number[-2:]}"
            corrected_num = parse_article_number_for_comparison(corrected)
            if min_article <= corrected_num <= max_article:
                warnings.append(f"Range-corrected: '{article_number}' → '{corrected}' (valid range: {min_article}-{max_article})")
                return corrected, warnings

    # Could not auto-correct
    warnings.append(f"Suspicious article number '{article_number}' for {code_id} (valid range: {min_article}-{max_article})")
    return article_number, warnings


def validate_and_correct_article_number(
    article_number: str,
    code_id: str,
    prev_article: Optional[str] = None,
    next_article: Optional[str] = None
) -> tuple[str, List[str]]:
    """
    Validate and potentially correct article numbers from source documents.

    Hybrid approach:
    1. If context available (prev/next articles), use context-based correction
    2. Fall back to range-based correction using known article ranges

    Context-based is more accurate for detecting issues like "1201" between "120" and "121".
    Range-based handles edge cases where context isn't available.

    Args:
        article_number: Raw article number from HTML
        code_id: Code identifier (e.g., 'TK_RF')
        prev_article: Previous article number (optional, for context)
        next_article: Next article number (optional, for context)

    Returns:
        Tuple of (corrected_article_number, warnings)
    """
    warnings: List[str] = []
    original = article_number

    # Step 1: If already has dot or hyphen, it's likely correct
    if '.' in article_number or '-' in article_number:
        return article_number, warnings

    # Step 2: Try context-based correction (more accurate)
    if prev_article and next_article:
        corrected, context_warnings = try_context_correction(article_number, prev_article, next_article)
        if context_warnings:
            warnings.extend(context_warnings)
            # If context-based correction worked, return it
            if corrected != original:
                return corrected, warnings

    # Step 3: Fall back to range-based correction
    corrected, range_warnings = try_range_correction(article_number, code_id)
    warnings.extend(range_warnings)

    return corrected, warnings


class BaseCodeImporter:
    """
    Import base legal code text from online sources.

    Supports:
    - consultant.ru: Free reference copy with HTML structure
    - pravo.gov.ru: Official publication (when available)
    """

    def __init__(self, timeout: Optional[int] = None):
        """
        Initialize the importer.

        Args:
            timeout: Request timeout in seconds (uses config.import_request_timeout if not specified)
        """
        self.timeout = timeout if timeout is not None else config.import_request_timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def fetch_consultant_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML from consultant.ru.

        Args:
            url: Full URL to the code page

        Returns:
            HTML content or None if failed
        """
        try:
            logger.info(f"Fetching from: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch from consultant.ru: {e}")
            return None

    def parse_consultant_html(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse consultant.ru HTML to extract article links.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        soup = BeautifulSoup(html, "html.parser")

        articles = []
        base_url = CODE_METADATA[code_id]["consultant_url"]

        # Find all article links in the table of contents
        # Consultant.ru uses a navigation structure with article links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Match article links like "Статья 1. Title" or "#doc-..."
            article_match = re.search(
                r"Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)?", text, re.IGNORECASE
            )

            if article_match:
                article_number = article_match.group(1)  # Preserve original format
                article_title = text

                # Build full URL for article page
                article_url = urljoin(base_url, href)

                articles.append(
                    {
                        "article_number": article_number,
                        "article_title": article_title,
                        "article_url": article_url,
                        "article_text": "",  # Will fetch separately
                    }
                )

        logger.info(f"Found {len(articles)} article links from consultant.ru table of contents")
        return {
            "code_id": code_id,
            "articles": articles,
            "source": "consultant.ru",
        }

    def fetch_article_text(self, article_url: str, article_number: str) -> str:
        """
        Fetch full text for a single article from its page.

        Args:
            article_url: URL to article page
            article_number: Article number

        Returns:
            Article text content
        """
        try:
            logger.debug(f"Fetching article {article_number} from {article_url}")
            response = self.session.get(article_url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for element in soup(["script", "style", "noscript", "nav", "footer", "header"]):
                element.decompose()

            # Find main content - consultant.ru typically uses specific containers
            main_content = (
                soup.find("div", class_="document-text")
                or soup.find("div", class_="docitem")
                or soup.find("article")
                or soup.find("main")
            )

            if main_content:
                # Extract text while preserving paragraphs
                paragraphs = []
                for p in main_content.find_all(["p", "div", "section"]):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:  # Filter out very short elements
                        paragraphs.append(text)

                article_text = "\n\n".join(paragraphs)
            else:
                # Fallback: get all text
                article_text = soup.get_text(separator="\n", strip=True)

            return article_text[:50000]  # Limit text length

        except Exception as e:
            logger.error(f"Failed to fetch article {article_number}: {e}")
            return ""

    def fetch_kremlin_html(self, bank_id: str) -> Optional[str]:
        """
        Fetch HTML from kremlin.ru (official publication portal).

        Args:
            bank_id: Kremlin bank ID (e.g., '7279' for Civil Code)

        Returns:
            HTML content or None if failed
        """
        url = f"http://www.kremlin.ru/acts/bank/{bank_id}/page/1"
        try:
            logger.info(f"Fetching from Kremlin: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch from kremlin.ru: {e}")
            return None

    def fetch_kremlin_html_all_pages(self, bank_id: str) -> List[str]:
        """
        Fetch ALL HTML pages from kremlin.ru (official publication portal).

        Some kremlin.ru pages have introductory content on early pages with
        actual articles starting on later pages. We check at least 3 pages before
        giving up.

        Args:
            bank_id: Kremlin bank ID (e.g., '7279' for Civil Code)

        Returns:
            List of HTML content strings (one per page), or empty list if failed
        """
        all_pages = []
        page_num = 1
        min_pages_to_check = 3  # Check at least 3 pages before giving up
        consecutive_empty_pages = 0
        max_consecutive_empty = 2  # Stop after 2 consecutive empty pages

        while True:
            url = f"http://www.kremlin.ru/acts/bank/{bank_id}/page/{page_num}"
            try:
                logger.info(f"Fetching page {page_num}: {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"

                # Check if this page has articles (look for article patterns in text)
                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text()
                has_articles = bool(re.search(r"Статья\s+\d+", text))

                if has_articles:
                    all_pages.append(response.text)
                    consecutive_empty_pages = 0
                else:
                    consecutive_empty_pages += 1
                    logger.info(f"Page {page_num} has no articles (empty count: {consecutive_empty_pages})")

                    # Stop if we've checked minimum pages AND found consecutive empty pages
                    if page_num >= min_pages_to_check and consecutive_empty_pages >= max_consecutive_empty:
                        logger.info(f"Stopping pagination after {consecutive_empty_pages} consecutive empty pages")
                        break

                    # Also stop if we've checked way too many pages without finding anything
                    if page_num >= 10 and not all_pages:
                        logger.warning(f"Checked {page_num} pages with no articles found, stopping")
                        break

                page_num += 1

                # Sleep to avoid rate limiting
                time.sleep(config.import_request_delay)

                # Safety limit to prevent infinite loops
                if page_num > 100:
                    logger.warning(f"Reached page limit (100), stopping pagination")
                    break

            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                # If we have some pages, return what we have
                if all_pages:
                    break
                # Otherwise give up after too many failures
                if page_num >= 5:
                    return []
                page_num += 1

        logger.info(f"Fetched {len(all_pages)} pages from kremlin.ru")
        return all_pages

    def parse_kremlin_html(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse kremlin.ru HTML to extract articles.

        The Kremlin source has full article text directly on the page, with
        articles marked by headers like "Статья 1. Title" and numbered paragraphs.

        Args:
            html: HTML content (single page string or list of pages)
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        # Handle multiple pages
        if isinstance(html, list):
            all_articles = []
            for i, page_html in enumerate(html):
                result = self._parse_single_kremlin_page(page_html, code_id)
                all_articles.extend(result.get("articles", []))
            logger.info(f"Parsed {len(all_articles)} articles from {len(html)} pages")
            return {
                "code_id": code_id,
                "articles": all_articles,
                "source": "kremlin.ru",
            }
        else:
            return self._parse_single_kremlin_page(html, code_id)

    def _parse_single_kremlin_page(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse a single kremlin.ru HTML page to extract articles.

        Collects raw articles first, then validates article numbers with context.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        soup = BeautifulSoup(html, "html.parser")

        raw_articles = []
        current_article = None
        current_paragraphs = []

        # Find all text elements - collect raw articles first
        for element in soup.find_all(["h4", "p", "div"]):
            text = element.get_text(strip=True)

            # Check if this is an article header
            article_match = re.match(
                r"^Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)$", text, re.IGNORECASE
            )

            if article_match:
                # Save previous article if exists
                if current_article and current_paragraphs:
                    current_article["article_text"] = "\n\n".join(current_paragraphs)
                    raw_articles.append(current_article)

                # Start new article (keep raw number for now)
                article_number = article_match.group(1)  # Preserve original format
                article_title = article_match.group(2).strip()

                current_article = {
                    "article_number": article_number,  # Raw number
                    "article_title": f"Статья {article_number}. {article_title}",
                    "article_text": "",
                }
                current_paragraphs = []

            elif current_article and text:
                # Check if this is a numbered paragraph (starts with number and period)
                # Or if it's content following an article header
                paragraph_match = re.match(r"^(\d+)\.\s*(.+)$", text)

                if paragraph_match:
                    # This is a numbered paragraph
                    current_paragraphs.append(text)
                elif (
                    text
                    and not text.startswith("Раздел")
                    and not text.startswith("Глава")
                    and not text.startswith("Подраздел")
                ):
                    # This is article content
                    current_paragraphs.append(text)

        # Don't forget the last article
        if current_article and current_paragraphs:
            current_article["article_text"] = "\n\n".join(current_paragraphs)
            raw_articles.append(current_article)

        # NOW validate and correct article numbers with context
        articles = []
        for i, raw_article in enumerate(raw_articles):
            raw_number = raw_article["article_number"]

            # Get context for validation
            prev_article = raw_articles[i - 1]["article_number"] if i > 0 else None
            next_article = raw_articles[i + 1]["article_number"] if i < len(raw_articles) - 1 else None

            # Validate with hybrid approach
            corrected_number, warnings = validate_and_correct_article_number(
                raw_number, code_id, prev_article, next_article
            )

            for warning in warnings:
                logger.warning(f"[{code_id}] {warning}")

            articles.append({
                **raw_article,
                "article_number": corrected_number,  # Use corrected number
            })

        return {
            "code_id": code_id,
            "articles": articles,
            "source": "kremlin.ru",
        }

    def import_code(self, code_id: str, source: str = "auto") -> Dict[str, Any]:
        """
        Import a legal code from specified source.

        Automatically falls back to alternative sources if the primary is unavailable:
        - kremlin (official) -> pravo (official) -> consultant (reference)

        Args:
            code_id: Code identifier (e.g., 'TK_RF')
            source: Source to import from ('auto', 'kremlin', 'pravo', 'consultant')

        Returns:
            Result dictionary
        """
        if code_id not in CODE_METADATA:
            return {"code_id": code_id, "status": "error", "error": f"Unknown code_id: {code_id}"}

        metadata = CODE_METADATA[code_id]

        # Handle multi-part codes
        if metadata.get("multi_part"):
            all_results = []
            for part_metadata in metadata["parts"]:
                part_code_id = part_metadata["code_id"]
                logger.info(
                    f"Importing part {part_metadata['part']} of {code_id} as {part_code_id}"
                )

                # Import each part separately
                result = self._import_single_code(part_code_id, part_metadata, source)
                all_results.append(result)

            # Return summary
            successful = sum(1 for r in all_results if r["status"] == "success")
            total_articles = sum(r.get("articles_saved", 0) for r in all_results)

            return {
                "code_id": code_id,
                "status": "success" if successful > 0 else "error",
                "parts_total": len(all_results),
                "parts_successful": successful,
                "total_articles_saved": total_articles,
                "results": all_results,
            }

        # Handle single-part codes
        return self._import_single_code(code_id, metadata, source)

    def _check_article_quality(self, articles: list, code_id: str) -> bool:
        """
        Check if parsed articles have acceptable quality.

        Quality metrics:
        - Too many "suspicious" article numbers (indicates source formatting issues)
        - Article count significantly different from expected range

        Args:
            articles: List of parsed articles
            code_id: Code identifier

        Returns:
            True if quality is acceptable, False otherwise
        """
        suspicious_count = 0
        range_info = KNOWN_ARTICLE_RANGES.get(code_id)

        for article in articles:
            article_number = article["article_number"]

            # Check if number looks suspicious (very large for this code)
            if range_info:
                min_article, max_article = range_info
                # Use multi-dot parser to handle articles like "20.3.1", "20.1.2"
                num = parse_article_number_for_comparison(article_number)
                if num > max_article * 1.5:  # More than 50% over max
                    suspicious_count += 1

        # If >10% of articles are suspicious, quality is poor
        if suspicious_count > len(articles) * 0.1:
            logger.warning(
                f"{suspicious_count}/{len(articles)} articles look suspicious for {code_id}, "
                f"trying alternative source"
            )
            return False

        return True

    def _import_single_code(
        self, code_id: str, metadata: Dict[str, Any], source: str
    ) -> Dict[str, Any]:
        """
        Import a single code (or one part of a multi-part code).

        Args:
            code_id: Code identifier
            metadata: Metadata dictionary for this code
            source: Source to import from

        Returns:
            Result dictionary
        """
        # Handle Constitution specially
        if metadata.get("is_constitution"):
            return self._import_constitution(code_id, metadata, source)

        # Auto-determine best available source
        if source == "auto":
            sources_to_try = ["kremlin", "pravo", "government"]
        else:
            sources_to_try = [source]

        # Try each source in priority order
        for src in sources_to_try:
            logger.info(f"Trying source: {src} for {code_id}")

            if src == "kremlin":
                if metadata.get("kremlin_bank"):
                    html_pages = self.fetch_kremlin_html_all_pages(metadata["kremlin_bank"])
                    if html_pages:
                        parsed = self.parse_kremlin_html(html_pages, code_id)
                        articles = parsed.get("articles", [])
                        if articles:
                            # Check quality before saving
                            if self._check_article_quality(articles, code_id):
                                saved = self.save_base_articles(code_id, articles, metadata)
                                return {
                                    "code_id": code_id,
                                    "status": "success",
                                    "pages_fetched": len(html_pages),
                                    "articles_found": len(articles),
                                    "articles_processed": len(articles),
                                    "articles_saved": saved,
                                    "source": "kremlin",
                                }
                            else:
                                # Quality check failed, try next source
                                logger.warning(f"Kremlin source quality check failed for {code_id}, trying next source")
                                continue

            elif src == "pravo":
                if metadata.get("pravo_nd"):
                    html_content = self.fetch_pravo_html(metadata["pravo_nd"])
                    if html_content:
                        parsed = self.parse_pravo_html(html_content, code_id)
                        articles = parsed.get("articles", [])
                        if articles:
                            # Check quality before saving
                            if self._check_article_quality(articles, code_id):
                                saved = self.save_base_articles(code_id, articles, metadata)
                                return {
                                    "code_id": code_id,
                                    "status": "success",
                                    "articles_found": len(articles),
                                    "articles_processed": len(articles),
                                    "articles_saved": saved,
                                    "source": "pravo",
                                }
                            else:
                                # Quality check failed, try next source
                                logger.warning(f"Pravo source quality check failed for {code_id}, trying next source")
                                continue

            elif src == "government":
                if metadata.get("government_url"):
                    html_pages = self.fetch_government_html_all_pages(metadata["government_url"])
                    if html_pages:
                        parsed = self.parse_government_html(html_pages, code_id)
                        articles = parsed.get("articles", [])
                        if articles:
                            # Check quality before saving
                            if self._check_article_quality(articles, code_id):
                                saved = self.save_base_articles(code_id, articles, metadata)
                                return {
                                    "code_id": code_id,
                                    "status": "success",
                                    "pages_fetched": len(html_pages),
                                    "articles_found": len(articles),
                                    "articles_processed": len(articles),
                                    "articles_saved": saved,
                                    "source": "government",
                                }
                            else:
                                # Quality check failed, try next source
                                logger.warning(f"Government source quality check failed for {code_id}, trying next source")
                                continue

        # All sources failed
        return {"code_id": code_id, "status": "error", "error": "Failed to fetch from any source or all sources had quality issues"}

    def _import_constitution(
        self, code_id: str, metadata: Dict[str, Any], source: str
    ) -> Dict[str, Any]:
        """
        Import Constitution from available sources.

        Args:
            code_id: Code identifier (should be 'KONST_RF')
            metadata: Metadata dictionary
            source: Source to import from

        Returns:
            Result dictionary
        """
        # Determine sources to try based on preference
        if source == "auto":
            sources_to_try = [
                ("pravo", metadata.get("pravo_nd")),
                ("kremlin", metadata.get("kremlin_url")),
            ]
        else:
            # Single source specified
            if source == "pravo":
                sources_to_try = [("pravo", metadata.get("pravo_nd"))]
            else:
                sources_to_try = [("kremlin", metadata.get("kremlin_url"))]

        # Try each source
        for src_name, src_value in sources_to_try:
            if not src_value:
                continue

            try:
                if src_name == "pravo":
                    logger.info(f"Fetching Constitution from pravo.gov.ru: {src_value}")
                    html_content = self.fetch_pravo_html(src_value)
                    if html_content:
                        parsed = self.parse_pravo_html(html_content, code_id)
                        articles = parsed.get("articles", [])
                        if articles:
                            saved = self.save_base_articles(code_id, articles, metadata)
                            return {
                                "code_id": code_id,
                                "status": "success",
                                "articles_found": len(articles),
                                "articles_processed": len(articles),
                                "articles_saved": saved,
                                "source": "pravo",
                            }

                elif src_name == "kremlin":
                    logger.info(f"Fetching Constitution from kremlin.ru: {src_value}")
                    response = self.session.get(src_value, timeout=self.timeout)
                    response.raise_for_status()
                    response.encoding = "utf-8"

                    parsed = self.parse_constitution(response.text, code_id)
                    articles = parsed.get("articles", [])
                    if articles:
                        saved = self.save_base_articles(code_id, articles, metadata)
                        return {
                            "code_id": code_id,
                            "status": "success",
                            "articles_found": len(articles),
                            "articles_processed": len(articles),
                            "articles_saved": saved,
                            "source": "kremlin",
                        }

            except Exception as e:
                logger.warning(f"Failed to fetch from {src_name}: {e}")
                continue

        return {
            "code_id": code_id,
            "status": "error",
            "error": "Failed to fetch from any available source",
        }

    def fetch_pravo_html(self, nd: str) -> Optional[str]:
        """
        Fetch HTML from pravo.gov.ru by document ID (nd).

        Args:
            nd: Document ID from pravo.gov.ru

        Returns:
            HTML content or None if failed
        """
        url = f"http://pravo.gov.ru/proxy/ips/?docbody=&nd={nd}"
        try:
            logger.info(f"Fetching from pravo.gov.ru: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch from pravo.gov.ru: {e}")
            return None

    def parse_pravo_html(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse pravo.gov.ru HTML to extract articles.

        Collects raw articles first, then validates article numbers with context.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        soup = BeautifulSoup(html, "html.parser")

        raw_articles = []

        # Pravo.gov.ru uses article headers like "Статья 1. Title"
        # Look for article patterns - collect raw first
        for element in soup.find_all(["h3", "h4", "p", "div"]):
            text = element.get_text(strip=True)
            article_match = re.match(
                r"^Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)$", text, re.IGNORECASE
            )

            if article_match:
                article_number = article_match.group(1)  # Preserve original format
                article_title = text

                # Find the article content (paragraphs following the header)
                content_paragraphs = []
                current_element = element.find_next_sibling(["p", "div"])
                while current_element:
                    para_text = current_element.get_text(strip=True)
                    # Stop at next article header
                    if re.match(r"^Статья\s+\d+", para_text):
                        break
                    if para_text and len(para_text) > 5:
                        content_paragraphs.append(para_text)
                    current_element = current_element.find_next_sibling(["p", "div"])

                raw_articles.append(
                    {
                        "article_number": article_number,
                        "article_title": article_title,
                        "article_text": "\n\n".join(content_paragraphs),
                    }
                )

        logger.info(f"Found {len(raw_articles)} raw articles from pravo.gov.ru")

        # NOW validate and correct article numbers with context
        articles = []
        for i, raw_article in enumerate(raw_articles):
            raw_number = raw_article["article_number"]

            # Get context for validation
            prev_article = raw_articles[i - 1]["article_number"] if i > 0 else None
            next_article = raw_articles[i + 1]["article_number"] if i < len(raw_articles) - 1 else None

            # Validate with hybrid approach
            corrected_number, warnings = validate_and_correct_article_number(
                raw_number, code_id, prev_article, next_article
            )

            for warning in warnings:
                logger.warning(f"[{code_id}] {warning}")

            articles.append({
                **raw_article,
                "article_number": corrected_number,  # Use corrected number
            })

        logger.info(f"Validated to {len(articles)} articles from pravo.gov.ru")
        return {
            "code_id": code_id,
            "articles": articles,
            "source": "pravo.gov.ru",
        }

    def fetch_government_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML from government.ru (single page).

        Args:
            url: Full URL to the document

        Returns:
            HTML content or None if failed
        """
        try:
            logger.info(f"Fetching from government.ru: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch from government.ru: {e}")
            return None

    def fetch_government_html_all_pages(self, url: str) -> List[str]:
        """
        Fetch ALL HTML pages from government.ru (handles pagination).

        Some government.ru pages have introductory content on page 1-2 with
        actual articles starting on page 3. We check at least 3 pages before
        giving up.

        Args:
            url: Full URL to the document

        Returns:
            List of HTML content strings (one per page), or empty list if failed
        """
        all_pages = []
        page_num = 1
        min_pages_to_check = 3  # Check at least 3 pages before giving up
        consecutive_empty_pages = 0
        max_consecutive_empty = 2  # Stop after 2 consecutive empty pages

        while True:
            page_url = f"{url}?page={page_num}" if page_num > 1 else url
            try:
                logger.info(f"Fetching page {page_num}: {page_url}")
                response = self.session.get(page_url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"

                # Check if this page has articles (look for article patterns in text)
                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text()
                has_articles = bool(re.search(r"Статья\s+\d+", text))

                if has_articles:
                    all_pages.append(response.text)
                    consecutive_empty_pages = 0
                else:
                    consecutive_empty_pages += 1
                    logger.info(f"Page {page_num} has no articles (empty count: {consecutive_empty_pages})")

                    # Stop if we've checked minimum pages AND found consecutive empty pages
                    if page_num >= min_pages_to_check and consecutive_empty_pages >= max_consecutive_empty:
                        logger.info(f"Stopping pagination after {consecutive_empty_pages} consecutive empty pages")
                        break

                    # Also stop if we've checked way too many pages without finding anything
                    if page_num >= 10 and not all_pages:
                        logger.warning(f"Checked {page_num} pages with no articles found, stopping")
                        break

                page_num += 1

                # Sleep to avoid rate limiting (government.ru is sensitive)
                time.sleep(config.import_request_delay)

                # Safety limit to prevent infinite loops
                if page_num > 100:
                    logger.warning(f"Reached page limit (100), stopping pagination")
                    break

            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                # If we have some pages, return what we have
                if all_pages:
                    break
                # Otherwise give up after too many failures
                if page_num >= 5:
                    return []
                page_num += 1

        logger.info(f"Fetched {len(all_pages)} pages from government.ru")
        return all_pages

    def parse_government_html(self, html: str | List[str], code_id: str) -> Dict[str, Any]:
        """
        Parse government.ru HTML to extract articles.

        Args:
            html: HTML content (single page string or list of pages)
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        # Handle multiple pages
        if isinstance(html, list):
            all_articles = []
            for i, page_html in enumerate(html):
                result = self._parse_single_government_page(page_html, code_id)
                all_articles.extend(result.get("articles", []))
            logger.info(f"Parsed {len(all_articles)} articles from {len(html)} pages")
            return {
                "code_id": code_id,
                "articles": all_articles,
                "source": "government.ru",
            }
        else:
            return self._parse_single_government_page(html, code_id)

    def _parse_single_government_page(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse a single government.ru HTML page to extract articles.

        Collects raw articles first, then validates article numbers with context.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        # Similar structure to Kremlin parser
        soup = BeautifulSoup(html, "html.parser")

        raw_articles = []
        current_article = None
        current_paragraphs = []

        for element in soup.find_all(["h3", "h4", "p", "div"]):
            text = element.get_text(strip=True)

            article_match = re.match(
                r"^Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)$", text, re.IGNORECASE
            )

            if article_match:
                # Save previous article
                if current_article and current_paragraphs:
                    current_article["article_text"] = "\n\n".join(current_paragraphs)
                    raw_articles.append(current_article)

                # Start new article (keep raw number for now)
                article_number = article_match.group(1)  # Preserve original format
                article_title = text

                current_article = {
                    "article_number": article_number,  # Raw number
                    "article_title": article_title,
                    "article_text": "",
                }
                current_paragraphs = []

            elif current_article and text:
                paragraph_match = re.match(r"^(\d+)\.\s*(.+)$", text)
                if paragraph_match:
                    current_paragraphs.append(text)
                elif text and not text.startswith("Раздел") and not text.startswith("Глава"):
                    current_paragraphs.append(text)

        # Don't forget the last article
        if current_article and current_paragraphs:
            current_article["article_text"] = "\n\n".join(current_paragraphs)
            raw_articles.append(current_article)

        # NOW validate and correct article numbers with context
        articles = []
        for i, raw_article in enumerate(raw_articles):
            raw_number = raw_article["article_number"]

            # Get context for validation
            prev_article = raw_articles[i - 1]["article_number"] if i > 0 else None
            next_article = raw_articles[i + 1]["article_number"] if i < len(raw_articles) - 1 else None

            # Validate with hybrid approach
            corrected_number, warnings = validate_and_correct_article_number(
                raw_number, code_id, prev_article, next_article
            )

            for warning in warnings:
                logger.warning(f"[{code_id}] {warning}")

            articles.append({
                **raw_article,
                "article_number": corrected_number,  # Use corrected number
            })

        return {
            "code_id": code_id,
            "articles": articles,
            "source": "government.ru",
        }

    def parse_constitution(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse Constitution HTML from kremlin.ru to extract articles.

        The Constitution has a different structure with sections and chapters.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        soup = BeautifulSoup(html, "html.parser")

        articles = []
        current_article = None
        current_paragraphs = []
        seen_articles = set()  # Track seen articles to avoid duplicates

        # Constitution uses "Статья X" format (articles 1-137 only)
        # Only process h3 elements which contain article headings
        # This avoids matching article references within article text
        for element in soup.find_all("h3"):
            text = element.get_text(strip=True)

            # Match "Статья X" or "Статья X*" format
            article_match = re.match(r"^Статья\s+(\d+)(\*?)$", text)

            if article_match:
                article_number = article_match.group(1)
                has_footnote = article_match.group(2)

                # Only accept valid Constitution article numbers (1-137)
                try:
                    article_num = int(article_number)
                    if article_num < 1 or article_num > 137:
                        logger.debug(f"Skipping article {article_number} (out of range 1-137)")
                        continue
                except ValueError:
                    continue

                # Skip if we've already processed this article number
                if article_number in seen_articles:
                    logger.debug(f"Skipping duplicate article {article_number}")
                    continue

                # Debug: log what we're accepting
                logger.debug(
                    f"Accepting article {article_number}{'*' if has_footnote else ''}: {text[:80]}"
                )

                # Mark this article as seen
                seen_articles.add(article_number)

                # Save previous article
                if current_article and current_paragraphs:
                    current_article["article_text"] = "\n\n".join(current_paragraphs)
                    articles.append(current_article)

                # Start new article - remove "*" from title for consistency
                article_title = f"Статья {article_number}" if has_footnote else text

                current_article = {
                    "article_number": article_number,
                    "article_title": article_title,
                    "article_text": "",
                }
                current_paragraphs = []

                # Get content following this heading (until next h3)
                current_element = element.find_next_sibling()
                while current_element:
                    # Stop at next h3 (next article)
                    if current_element.name == "h3":
                        break

                    # Only collect text from p and div elements
                    if current_element.name in ["p", "div"]:
                        para_text = current_element.get_text(strip=True)
                        if para_text and len(para_text) > 5:
                            current_paragraphs.append(para_text)

                    current_element = current_element.find_next_sibling()

        # Don't forget the last article
        if current_article and current_paragraphs:
            current_article["article_text"] = "\n\n".join(current_paragraphs)
            articles.append(current_article)

        logger.info(f"Found {len(articles)} articles in Constitution")
        return {
            "code_id": code_id,
            "articles": articles,
            "source": "kremlin.ru",
        }

    def save_base_articles(
        self, code_id: str, articles: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> int:
        """
        Save base articles to code_article_versions table.

        Uses "delete + upsert" strategy for data freshness:
        1. Delete all existing articles for this code (clean slate)
        2. Insert fresh articles using UPSERT (handles duplicates within batch)

        The UPSERT handles cases where the same article number appears multiple
        times across different pages (e.g., kremlin.ru pagination).

        Args:
            code_id: Code identifier
            articles: List of article dictionaries
            metadata: Metadata dictionary for this code

        Returns:
            Number of articles saved
        """
        saved = 0
        original_date = metadata.get("original_date")

        # Step 1: Delete all existing articles for this code
        try:
            with get_db_connection() as conn:
                delete_query = text(
                    """
                    DELETE FROM code_article_versions
                    WHERE code_id = :code_id
                """
                )
                result = conn.execute(delete_query, {"code_id": code_id})
                deleted_count = result.rowcount
                logger.info(f"Deleted {deleted_count} existing articles for {code_id}")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete existing articles for {code_id}: {e}")
            return 0

        # Step 2: Insert fresh articles
        for article in articles:
            try:
                with get_db_connection() as conn:
                    insert_query = text(
                        """
                        INSERT INTO code_article_versions (
                            code_id,
                            article_number,
                            version_date,
                            article_text,
                            article_title,
                            amendment_eo_number,
                            amendment_date,
                            is_current,
                            is_repealed,
                            text_hash
                        ) VALUES (
                            :code_id,
                            :article_number,
                            :version_date,
                            :article_text,
                            :article_title,
                            :amendment_eo_number,
                            :amendment_date,
                            :is_current,
                            :is_repealed,
                            :text_hash
                        )
                        ON CONFLICT (code_id, article_number, version_date)
                        DO UPDATE SET
                            article_text = EXCLUDED.article_text,
                            article_title = EXCLUDED.article_title,
                            amendment_eo_number = EXCLUDED.amendment_eo_number,
                            is_current = EXCLUDED.is_current,
                            is_repealed = EXCLUDED.is_repealed,
                            text_hash = EXCLUDED.text_hash
                    """
                    )

                    conn.execute(
                        insert_query,
                        {
                            "code_id": code_id,
                            "article_number": article["article_number"],
                            "version_date": original_date,
                            "article_text": article["article_text"],
                            "article_title": article["article_title"],
                            "amendment_eo_number": metadata.get("eo_number"),
                            "amendment_date": original_date,
                            "is_current": True,
                            "is_repealed": False,
                            "text_hash": "",
                        },
                    )
                    conn.commit()
                    saved += 1
                    logger.debug(f"Saved article {article['article_number']}")

            except Exception as e:
                logger.error(f"Failed to save article {article.get('article_number')}: {e}")

        return saved

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import base legal codes from official sources")
    parser.add_argument("--code", choices=list(CODE_METADATA.keys()), help="Code to import")
    parser.add_argument("--all", action="store_true", help="Import all codes")
    parser.add_argument(
        "--source",
        choices=["auto", "kremlin", "pravo", "government"],
        default="auto",
        help="Source to import from (default: auto - tries kremlin, then pravo, then government)",
    )
    parser.add_argument("--list", action="store_true", help="List available codes")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set UTF-8 for Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    # List codes
    if args.list:
        print("Available codes:")
        print("-" * 60)
        for code_id, metadata in CODE_METADATA.items():
            print(f"  {code_id}: {metadata['name']}")
            if metadata.get("multi_part"):
                parts = metadata.get("parts", [])
                print(f"    Parts: {len(parts)} (multi-part code)")
                for part in parts:
                    print(
                        f"      - Part {part['part']}: code_id={part['code_id']}, kremlin_bank={part.get('kremlin_bank')}"
                    )
            else:
                print(f"    EO Number: {metadata.get('eo_number')}")
                print(f"    Original Date: {metadata.get('original_date')}")
                print(
                    f"    Sources: kremlin={bool(metadata.get('kremlin_bank'))}, "
                    f"pravo={bool(metadata.get('pravo_nd'))}, "
                    f"government={bool(metadata.get('government_url'))}"
                )
            print()
        return

    # Import codes
    with BaseCodeImporter() as importer:
        if args.code:
            result = importer.import_code(args.code, args.source)
            print(f"\n{'='*60}")
            print(f"Import Results: {result['code_id']}")
            print(f"{'='*60}")
            print(f"Status: {result['status']}")

            if result["status"] == "success":
                # Handle multi-part code results
                if result.get("parts_total"):
                    print(
                        f"Parts: {result['parts_successful']}/{result['parts_total']} imported successfully"
                    )
                    print(f"Total Articles Saved: {result['total_articles_saved']}")
                    for i, part_result in enumerate(result.get("results", [])):
                        print(
                            f"  Part {i+1}: {part_result['code_id']} - "
                            f"{part_result.get('articles_saved', 0)} articles "
                            f"({part_result['source']})"
                        )
                else:
                    # Single-part code
                    if result.get("pages_fetched"):
                        print(f"Pages Fetched: {result['pages_fetched']}")
                    print(f"Articles Found: {result['articles_found']}")
                    print(f"Articles Processed: {result.get('articles_processed', 0)}")
                    print(f"Articles Saved: {result['articles_saved']}")
                    print(f"Source: {result['source']}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
            print(f"{'='*60}")

        elif args.all:
            print("Importing all codes...")
            results = []
            for code_id in CODE_METADATA.keys():
                result = importer.import_code(code_id, args.source)
                results.append(result)
                print(f"  {code_id}: {result['status']}")

            print(f"\n{'='*60}")
            print("Summary")
            print(f"{'='*60}")
            successful = sum(1 for r in results if r["status"] == "success")
            print(f"Successful: {successful}/{len(results)}")

        else:
            parser.print_help()


if __name__ == "__main__":
    main()
