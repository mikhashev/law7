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
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

from scripts.core.db import get_db_connection
from scripts.core.config import config
from scripts.core.article_parser import ArticleNumberParser, ArticleNumber

logger = logging.getLogger(__name__)

# Singleton instance of the article parser for use throughout the module
_article_parser = ArticleNumberParser()

# Module-level cache for consultant.ru article numbers
# Key: code_id, Value: set of article numbers
_consultant_articles_cache: Dict[str, set[str]] = {}

# Consultant.ru document IDs for verification
# Used to cross-verify article numbers after import from official sources
CONSULTANT_DOC_IDS = {
    'KONST_RF': 'cons_doc_LAW_28399',  # Constitution
    'GK_RF': 'cons_doc_LAW_5142',     # Civil Code Part 1
    'GK_RF_2': 'cons_doc_LAW_9027',    # Civil Code Part 2
    'GK_RF_3': 'cons_doc_LAW_34154',    # Civil Code Part 3
    'GK_RF_4': 'cons_doc_LAW_64629',    # Civil Code Part 4
    'UK_RF': 'cons_doc_LAW_10699',      # Criminal Code
    'TK_RF': 'cons_doc_LAW_34683',      # Labor Code
    'NK_RF': 'cons_doc_LAW_19671',      # Tax Code Part 1
    'NK_RF_2': 'cons_doc_LAW_28165',    # Tax Code Part 2
    'KoAP_RF': 'cons_doc_LAW_34661',    # Administrative Code
    'SK_RF': 'cons_doc_LAW_8982',      # Family Code
    'ZhK_RF': 'cons_doc_LAW_51057',     # Housing Code
    'ZK_RF': 'cons_doc_LAW_33773',      # Land Code
    'APK_RF': 'cons_doc_LAW_37800',     # Arbitration Procedure Code
    'GPK_RF': 'cons_doc_LAW_39570',     # Civil Procedure Code
    'UPK_RF': 'cons_doc_LAW_34481',     # Criminal Procedure Code
    'BK_RF': 'cons_doc_LAW_19702',      # Budget Code
    'GRK_RF': 'cons_doc_LAW_51040',     # Urban Planning Code
    'UIK_RF': 'cons_doc_LAW_12940',     # Criminal Executive Code
    'VZK_RF': 'cons_doc_LAW_13744',     # Air Code
    'VDK_RF': 'cons_doc_LAW_60683',     # Water Code
    'LK_RF': 'cons_doc_LAW_64299',      # Forest Code
    'KAS_RF': 'cons_doc_LAW_176147',     # Administrative Procedure Code
}


# Code metadata for import
# Priority: kremlin (official) -> pravo (official) -> government (official)
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
    'BK_RF': (1, 307),         # Budget Code (30 chapters, articles go up to 307)
    'GRK_RF': (1, 120),
    'UIK_RF': (1, 200),
    'VZK_RF': (1, 150),
    'VDK_RF': (1, 100),
    'LK_RF': (1, 120),
    'KAS_RF': (1, 350),
}


# Expected article counts for validation (based on official sources)
# These are approximate minimum counts - parsing fewer than this triggers warnings
# Format: code_id -> expected_minimum_count
KNOWN_ARTICLE_COUNTS = {
    'KONST_RF': 137,      # Constitution has ~137 articles
    'GK_RF': 453,         # Civil Code Part 1
    'GK_RF_2': 656,       # Civil Code Part 2 (1109 - 454 + 1)
    'GK_RF_3': 115,       # Civil Code Part 3 (1224 - 1110 + 1)
    'GK_RF_4': 327,       # Civil Code Part 4 (1551 - 1225 + 1)
    'UK_RF': 361,         # Criminal Code
    'TK_RF': 424,         # Labor Code
    'NK_RF': 142,         # Tax Code Part 1
    'NK_RF_2': 290,       # Tax Code Part 2 (432 - 143 + 1)
    'KoAP_RF': 350,       # Administrative Code (estimate, has ~350+ articles)
    'SK_RF': 170,         # Family Code
    'ZhK_RF': 165,        # Housing Code
    'ZK_RF': 85,          # Land Code
    'APK_RF': 418,        # Arbitration Procedure Code
    'GPK_RF': 494,        # Civil Procedure Code
    'UPK_RF': 553,        # Criminal Procedure Code
    'BK_RF': 307,         # Budget Code (30 chapters, articles up to 307)
    'GRK_RF': 120,        # Urban Planning Code
    'UIK_RF': 200,        # Criminal Executive Code
    'VZK_RF': 150,        # Air Code
    'VDK_RF': 100,        # Water Code
    'LK_RF': 120,         # Forest Code
    'KAS_RF': 350,        # Administrative Procedure Code
}

# Acceptable deviation from expected count (percentage)
# Below this threshold triggers warnings (severe parsing issues)
ACCEPTABLE_COUNT_DEVIATION = 0.50  # 50% of expected count (warn only if missing half or more)


def validate_article_count(code_id: str, article_count: int) -> List[str]:
    """
    Validate that the parsed article count is acceptable.

    Warns if we parsed significantly fewer articles than expected,
    which could indicate missing pages, parsing errors, or source changes.

    Args:
        code_id: Code identifier (e.g., 'TK_RF')
        article_count: Number of articles parsed

    Returns:
        List of warning messages (empty if count is acceptable)
    """
    warnings: List[str] = []
    expected_min = KNOWN_ARTICLE_COUNTS.get(code_id)

    if not expected_min:
        # No expected count for this code
        return warnings

    threshold = int(expected_min * ACCEPTABLE_COUNT_DEVIATION)

    if article_count < threshold:
        warnings.append(
            f"Article count {article_count} is below {ACCEPTABLE_COUNT_DEVIATION * 100:.0f}% "
            f"of expected {expected_min} for {code_id} (threshold: {threshold}). "
            f"This may indicate missing pages or parsing errors."
        )
    elif article_count < expected_min:
        warnings.append(
            f"Article count {article_count} is below expected {expected_min} for {code_id}, "
            f"but within acceptable range."
        )

    return warnings


def parse_article_number_for_comparison(article_number: str) -> float:
    """
    Parse article number for range comparison.
    Extracts base number (before first dot) for multi-dot formats.

    This allows "20.1.2" to be compared against range [1, 890] using value 20.0.
    Python's float("20.1.2") raises ValueError, so we extract the base number.

    Args:
        article_number: Article number like "1", "20.3", "20.3.1", "20.3.1.2", "20-1"

    Returns:
        Float value for range comparison (base number only)
    """
    # Extract base number (everything before first dot, or full number if no dots)
    base_number = article_number.split('.')[0]

    # For hyphenated articles like "12316-1", extract the base part before the hyphen
    if '-' in base_number:
        base_number = base_number.split('-')[0]

    return float(base_number) if base_number.isdigit() else 0.0


def parse_article_number_structured(article_number: str) -> Optional[ArticleNumber]:
    """
    Parse article number using the structured ArticleNumber parser.

    Provides structured access to article number components (base, insertion, subdivision).
    Returns None if the article number format is not recognized by the parser.

    This is useful for:
    - Extracting article components for database storage
    - Validating article number format
    - Building article hierarchies

    Args:
        article_number: Article number as string (e.g., "25", "25.12", "25.12-1")

    Returns:
        ArticleNumber object if parsing succeeds, None otherwise

    Examples:
        >>> parse_article_number_structured("25.12-1")
        ArticleNumber(base=25, insertion=12, subdivision=1)
        >>> parse_article_number_structured("2512-1")
        ArticleNumber(base=2512, insertion=None, subdivision=1)
        >>> parse_article_number_structured("invalid")
        None
    """
    try:
        return _article_parser.parse(article_number)
    except ValueError:
        # Article number doesn't match the standard pattern
        # This is OK - the existing validation logic will handle it
        return None


def is_valid_article_number_format(article_number: str) -> bool:
    """
    Check if an article number matches the standard format.

    Uses the ArticleNumberParser to validate the format.

    Args:
        article_number: Article number as string to validate

    Returns:
        True if the article number matches the standard format, False otherwise

    Examples:
        >>> is_valid_article_number_format("25.12-1")
        True
        >>> is_valid_article_number_format("25-1")
        True
        >>> is_valid_article_number_format("invalid")
        False
    """
    return _article_parser.is_valid(article_number)


def try_context_correction(
    article_number: str,
    prev_article: Optional[str],
    next_article: Optional[str],
    code_id: Optional[str] = None
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

    # Convert multi-dot hierarchy articles (e.g., "10.5.1" → "1051")
    # Single-dot articles like "1.31" are valid legal notation - preserve them
    if '.' in article_number:
        dot_count = article_number.count('.')
        if dot_count >= 2:
            # Multi-dot = HTML hierarchy encoding
            # Format: "20.3.1" means article 203, part 1 (multi-level hierarchy)
            dotless = article_number.replace('.', '')
            if dotless.isdigit() and 2 < len(dotless) < 7:
                warnings.append(f"Converted multi-dot '{article_number}' to '{dotless}'")
                article_number = dotless
        # Single-dot articles (like "1.31") are preserved - they're valid legal notation

    # Hyphenated articles WITHOUT dots need correction (e.g., "521-1" → "52.1-1")
    # Hyphenated articles WITH dots are already correct (e.g., "52.1-1" is correct)
    if '-' in article_number and '.' not in article_number:
        # Continue to correction logic below for hyphenated articles missing dots
        pass
    elif '-' in article_number:
        # Already has dots, return as-is
        return article_number, warnings

    # Check if article_number is a pure number
    if not article_number.isdigit():
        # Special handling for hyphenated articles missing dots (e.g., "521-1" → "52.1-1")
        if '-' in article_number:
            logger.debug(f"Processing hyphenated article: '{article_number}' between '{prev_article}' and '{next_article}'")
            # Extract base part and hyphen part
            base_part = article_number.split('-')[0]
            hyphen_suffix = '-' + article_number.split('-')[1]

            if base_part.isdigit() and len(base_part) >= 3:
                # Check if base part matches previous article (same article, different appendix)
                # Handle two cases:
                # 1. Previous article is a pure digit: "12316" (original source format)
                # 2. Previous article has been corrected: "123.16" (dot notation)
                if prev_article:
                    if prev_article.isdigit():
                        # Case 1: Previous article is pure digit - direct comparison
                        if int(prev_article) == int(base_part):
                            # Previous article is the same base, so this is an appendix/variant
                            # Keep hyphenated format as-is if base is within reasonable bounds
                            range_info = KNOWN_ARTICLE_RANGES.get(code_id)
                            if range_info:
                                min_article, max_article = range_info
                                if min_article <= int(base_part) <= max_article * 10:
                                    return article_number, warnings
                    elif '.' in prev_article:
                        # Case 2: Previous article has dot notation - extract base and compare
                        # Example: prev="123.16", base_part="12316" → both have base "123"
                        prev_base = prev_article.split('.')[0]
                        if prev_base.isdigit() and base_part.startswith(prev_base):
                            # Check if the rest of base_part is a valid subdivision
                            remainder = base_part[len(prev_base):]
                            # If remainder makes it a subdivision (e.g., "16" makes it "123.16")
                            if remainder.isdigit() and len(remainder) <= 2:
                                # Reconstruct using previous article's base format (without hyphen suffix)
                                # If prev_article has hyphen (e.g., "123.16-1"), extract just "123.16"
                                prev_base_format = prev_article.split('-')[0] if '-' in prev_article else prev_article
                                # Construct the corrected base using prev_base_format + remainder
                                # Example: prev="123.16-1", base_part="12316" → prev_base_format="123.16", remainder="16"
                                # → corrected_base = "123.16"
                                corrected_base = prev_base_format
                                # Add the current hyphen suffix
                                corrected = f"{corrected_base}-{article_number.split('-')[1]}"
                                return corrected, warnings

                # Try to correct the base part using context
                try:
                    prev_num = parse_article_number_for_comparison(prev_article)
                    next_num = parse_article_number_for_comparison(next_article)

                    # Generate all valid candidates for the base part
                    candidates = _generate_dot_candidates(base_part)

                    # If previous article has dot notation, extract its base and prefer matching candidates
                    # Example: prev="123.7" should prefer "123.8" over "12.38" for base "1238"
                    prev_candidate_base = None
                    if '.' in prev_article:
                        prev_candidate_base = prev_article.split('.')[0]

                    # Try each candidate and see if it fits in context
                    # Collect all valid candidates, then prefer those matching previous article's base
                    valid_candidates = []
                    for candidate_base in candidates:
                        corrected_num = parse_article_number_for_comparison(candidate_base)

                        logger.debug(f"Trying correction: '{base_part}' → '{candidate_base}' (prev={prev_num}, next={next_num}, corrected={corrected_num})")

                        # Check if corrected fits between neighbors
                        if prev_num <= corrected_num <= next_num:
                            valid_candidates.append(candidate_base)

                    # If we have valid candidates, prefer those matching previous article's base
                    if valid_candidates:
                        if prev_candidate_base:
                            # Filter candidates with same base as previous article
                            matching_candidates = [c for c in valid_candidates if c.split('.')[0] == prev_candidate_base]
                            if matching_candidates:
                                # Prefer matching candidate
                                corrected = matching_candidates[0] + hyphen_suffix
                                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                                return corrected, warnings

                        # No matching base, use first valid candidate
                        corrected = valid_candidates[0] + hyphen_suffix
                        warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                        return corrected, warnings
                except (ValueError, IndexError) as e:
                    logger.debug(f"Correction failed for '{article_number}': {e}")
                    pass

    # Continue to general context correction for all article numbers (including pure digits)
    # Don't return early here - let the dot insertion logic handle pure-digit numbers like 601 → 60.1

    # IMPORTANT: Before accepting an article as valid, check if it could be a sub-article of the previous article
    # Example: "601" between "60" and "602" should become "60.1" (not stay as "601")
    # BUT: "232" between "23.1" and "233" should stay as "232" (not become "23.2")
    # The key distinction: only convert if the ORIGINAL number doesn't fit between neighbors
    if prev_article and article_number.isdigit() and len(article_number) >= 3:
        prev_base = prev_article.split('.')[0] if '.' in prev_article else prev_article
        # If article_number starts with prev_base, it might be a sub-article
        if article_number.startswith(prev_base) and len(article_number) > len(prev_base):
            # Try converting to sub-article format (e.g., "601" → "60.1")
            candidate = f"{prev_base}.{article_number[len(prev_base):]}"
            try:
                # Use ArticleNumber comparison for proper ordering
                prev_parsed = _article_parser.parse(prev_article)
                cand_parsed = _article_parser.parse(candidate)
                next_parsed = _article_parser.parse(next_article)

                # CRITICAL FIX: Only apply sub-article conversion if the ORIGINAL number doesn't fit
                # This prevents cascade errors like "232" → "23.2" when it's between "23.1" and "233"
                original_parsed = _article_parser.parse(article_number)
                if not (prev_parsed < original_parsed < next_parsed):
                    # Original doesn't fit, but candidate does - apply conversion
                    if prev_parsed < cand_parsed < next_parsed:
                        warnings.append(f"Context-corrected: '{article_number}' → '{candidate}' (between {prev_article} and {next_article})")
                        return candidate, warnings
            except ValueError:
                pass

    # If current article fits between neighbors, it's correct
    # Use ArticleNumber parser for proper hierarchy-aware comparison
    # This correctly handles: "12" < "12.2" < "13"
    try:
        current_parsed = _article_parser.parse(article_number)
        prev_parsed = _article_parser.parse(prev_article)
        next_parsed = _article_parser.parse(next_article)

        # Check if current article fits between neighbors using ArticleNumber comparison
        if prev_parsed < current_parsed < next_parsed:
            return article_number, warnings
    except ValueError:
        pass

    # Try inserting a dot before the last digit (e.g., "71" → "7.1", "122" → "12.2")
    if len(article_number) > 1:
        corrected = f"{article_number[:-1]}.{article_number[-1]}"
        try:
            corrected_parsed = _article_parser.parse(corrected)
            prev_parsed = _article_parser.parse(prev_article)
            next_parsed = _article_parser.parse(next_article)

            # Check if corrected article fits between neighbors using ArticleNumber comparison
            if prev_parsed < corrected_parsed < next_parsed:
                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                return corrected, warnings
        except ValueError:
            pass

    # Try inserting a dot before the last 2 digits (e.g., "1256" → "12.56" or "125.6")
    if len(article_number) > 2:
        # Try "125.6"
        corrected = f"{article_number[:-1]}.{article_number[-1:]}"
        try:
            corrected_parsed = _article_parser.parse(corrected)
            prev_parsed = _article_parser.parse(prev_article)
            next_parsed = _article_parser.parse(next_article)
            if prev_parsed < corrected_parsed < next_parsed:
                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                return corrected, warnings
        except ValueError:
            pass

        # Try "12.56"
        corrected = f"{article_number[:-2]}.{article_number[-2:]}"
        try:
            corrected_parsed = _article_parser.parse(corrected)
            prev_parsed = _article_parser.parse(prev_article)
            next_parsed = _article_parser.parse(next_article)
            if prev_parsed < corrected_parsed < next_parsed:
                warnings.append(f"Context-corrected: '{article_number}' → '{corrected}' (between {prev_article} and {next_article})")
                return corrected, warnings
        except ValueError:
            pass

    # Could not correct with context
    return article_number, warnings


def _generate_dot_candidates(article_number: str) -> List[str]:
    """
    Generate all valid dot-notation candidates for a malformed article number.

    This helper function generates possible corrected versions of article numbers
    by inserting dots in different positions. The candidates are ordered by
    priority (most likely patterns first).

    Examples:
        "511" → ["51.1", "5.1.1", "511"]
        "521-1" → ["52.1-1", "5.2.1-1", "521-1"]
        "41" → ["4.1", "41"]

    Args:
        article_number: Raw article number that may be missing dots

    Returns:
        List of candidate article numbers, ordered by priority
    """
    candidates = []

    if not article_number.replace('-', '').replace('.', '').isdigit():
        return [article_number]  # Skip non-numeric

    # Split out hyphenated part if present
    base_part = article_number.split('-')[0]
    hyphen_part = f"-{article_number.split('-')[1]}" if '-' in article_number else ""

    # If already has dots, return as-is (no correction needed)
    if '.' in article_number:
        return [article_number]

    # Generate candidates based on length
    if len(base_part) == 2:
        # "41" → "4.1" (2-digit pattern)
        if base_part[0] != '0':  # Don't convert "01" to "0.1"
            candidates.append(f"{base_part[0]}.{base_part[1]}{hyphen_part}")

    elif len(base_part) == 3:
        # XY.Z pattern: "511" → "51.1" (PRIORITY - 2-digit base)
        candidates.append(f"{base_part[:2]}.{base_part[2]}{hyphen_part}")
        # X.Y.Z pattern: "511" → "5.1.1" (fallback)
        candidates.append(f"{base_part[0]}.{base_part[1]}.{base_part[2]}{hyphen_part}")

    elif len(base_part) == 4:
        # For 4-digit numbers, try multiple patterns
        # "1256" → "12.5.6" (X.Y.Z with 2-digit base)
        candidates.append(f"{base_part[:2]}.{base_part[2]}.{base_part[3]}{hyphen_part}")
        # "1256" → "12.56" (2-digit base + 2-digit subsection)
        candidates.append(f"{base_part[:2]}.{base_part[2:]}{hyphen_part}")
        # "1256" → "125.6" (3-digit base + 1-digit subsection)
        candidates.append(f"{base_part[:3]}.{base_part[3]}{hyphen_part}")

    elif len(base_part) == 5:
        # For 5-digit numbers, try multi-level patterns
        # "20312" → "20.3.12" (2-digit base + 2-level subsection)
        candidates.append(f"{base_part[:2]}.{base_part[2]}.{base_part[3:]}{hyphen_part}")
        # "20312" → "203.1.2" (3-digit base + 2-level subsection)
        candidates.append(f"{base_part[:3]}.{base_part[3]}.{base_part[4]}{hyphen_part}")
        # "21410" → "214.10" (3-digit base + 2-digit subsection)
        candidates.append(f"{base_part[:3]}.{base_part[3:]}{hyphen_part}")

    elif len(base_part) == 6:
        # For 6-digit numbers, try multi-level patterns
        # "123412" → "12.34.12" (2-digit base + 2-digit insertion + 2-digit subsection)
        candidates.append(f"{base_part[:2]}.{base_part[2:4]}.{base_part[4:]}{hyphen_part}")
        # "123412" → "123.4.12" (3-digit base + 1-digit insertion + 2-digit subsection)
        candidates.append(f"{base_part[:3]}.{base_part[3]}.{base_part[4:]}{hyphen_part}")
        # "123412" → "1234.12" (4-digit base + 2-digit subsection) - PRIORITY
        candidates.append(f"{base_part[:4]}.{base_part[4:]}{hyphen_part}")

    # Always include original as fallback
    candidates.append(article_number)

    return candidates


def try_consultant_reference_correction(
    article_number: str,
    code_id: str,
    consultant_articles: Optional[set[str]] = None,
    prev_article: Optional[str] = None,
    next_article: Optional[str] = None
) -> tuple[Optional[str], List[str]]:
    """
    Attempt to correct article number using consultant.ru reference.

    Uses consultant.ru's authoritative article numbers to disambiguate conversions.
    For example, "1051" could be "105.1" or "10.51" - we check which one
    exists in consultant.ru and use that.

    CRITICAL: If the original article_number fits in the sequence (between prev and next),
    it is considered correct and no correction is applied. This prevents false positives
    like "231" being corrected to "23.1" when "231" is the correct article in context.

    Args:
        article_number: Raw article number from HTML (e.g., "1051")
        code_id: Code identifier (e.g., 'BK_RF')
        consultant_articles: Set of valid article numbers from consultant.ru
                            (will be fetched from cache if not provided)
        prev_article: Previous article number (for sequence validation)
        next_article: Next article number (for sequence validation)

    Returns:
        Tuple of (corrected_number or None, warnings)
        Returns (None, []) if consultant_articles is not available or no match found
    """
    warnings: List[str] = []

    # Skip if article already has dots (already formatted)
    if '.' in article_number:
        return None, warnings

    # Skip if article is not a pure number
    if not article_number.isdigit():
        return None, warnings

    # Fetch consultant articles if not provided
    if consultant_articles is None:
        # Check module-level cache first
        if code_id in _consultant_articles_cache:
            consultant_articles = _consultant_articles_cache[code_id]
        else:
            if code_id not in CONSULTANT_DOC_IDS:
                return None, warnings
            doc_id = CONSULTANT_DOC_IDS[code_id]
            fetched_articles = scrape_article_numbers_from_consultant(doc_id)
            # ALWAYS cache, even if empty (prevents retry loop on failed scrapes)
            consultant_articles = set(fetched_articles) if fetched_articles else set()
            _consultant_articles_cache[code_id] = consultant_articles
            if not fetched_articles:
                logger.warning(f"No articles found for {code_id}, caching empty result to prevent retry loop")
                return None, warnings
            logger.info(f"Cached {len(consultant_articles)} consultant articles for {code_id}")

    # CRITICAL FIX: Check if original article fits in sequence before correcting
    # If article_number fits between prev and next, it's already correct!
    # Example: "231" with prev=230, next=232 is article 231, NOT 23.1
    if prev_article and next_article:
        try:
            original_parsed = _article_parser.parse(article_number)
            prev_parsed = _article_parser.parse(prev_article)
            next_parsed = _article_parser.parse(next_article)
            # If original fits in sequence, skip correction
            if prev_parsed < original_parsed < next_parsed:
                logger.debug(
                    f"[{code_id}] Article '{article_number}' fits in sequence "
                    f"({prev_article} < {article_number} < {next_article}), "
                    f"skipping consultant correction"
                )
                return None, warnings
        except ValueError:
            # If parsing fails, continue to consultant correction
            pass

    # Generate all possible dot-notation candidates
    candidates = _generate_dot_candidates(article_number)

    # Check which candidates exist in consultant.ru
    matching_candidates = []
    for candidate in candidates:
        if candidate in consultant_articles:
            matching_candidates.append(candidate)

    # If exactly one match, use it
    if len(matching_candidates) == 1:
        corrected = matching_candidates[0]
        warnings.append(
            f"Consultant-corrected: '{article_number}' -> '{corrected}' "
            f"(found in consultant.ru)"
        )
        return corrected, warnings

    # If multiple matches, prefer the one with MORE dots (proper sub-article format)
    # Example: prefer "23.1" (1 dot) over "231" (0 dots)
    # The original dotless format should only be used as fallback
    if len(matching_candidates) > 1:
        # Separate into corrected (with dots) and original (without dots)
        with_dots = [c for c in matching_candidates if '.' in c]

        # If we have corrected versions with dots, prefer those
        # Sort by MORE dots first (more specific sub-article format)
        if with_dots:
            with_dots.sort(key=lambda x: x.count('.'), reverse=True)
            corrected = with_dots[0]
        else:
            # Only have dotless versions, use first
            corrected = matching_candidates[0]

        warnings.append(
            f"Consultant-corrected: '{article_number}' -> '{corrected}' "
            f"(multiple matches, chose {len(matching_candidates)} options)"
        )
        return corrected, warnings

    # No match found in consultant.ru
    return None, warnings


def try_range_correction(
    article_number: str,
    code_id: str,
    prev_article: Optional[str] = None,
    next_article: Optional[str] = None
) -> tuple[str, List[str]]:
    """
    Attempt to correct article number using known article ranges.

    Simplified version that generates candidate corrections and validates them
    using the ArticleNumberParser.

    Args:
        article_number: Raw article number from HTML
        code_id: Code identifier (e.g., 'TK_RF')
        prev_article: Previous article number (optional, for context-aware correction)
        next_article: Next article number (optional, for context-aware correction)

    Returns:
        Tuple of (corrected_number, warnings)
    """
    warnings: List[str] = []

    # Get the valid range for this code
    range_info = KNOWN_ARTICLE_RANGES.get(code_id)
    if not range_info:
        # Unknown code - can't validate, return as-is
        return article_number, warnings

    min_article, max_article = range_info

    # Step 1: If article number already has dots (with or without hyphens), it's likely correct
    if '.' in article_number:
        return article_number, warnings

    # Step 2: Check if it's a pure number within valid range (no correction needed)
    # This prevents converting valid sequential articles like 11, 12, 71 to 1.1, 1.2, 7.1
    # Use strict max_article range to catch sub-articles with deleted parent articles
    # Example: 1061 should become 106.1 (article 106 was deleted, but 106.1 remains)
    if article_number.isdigit():
        num = int(article_number)
        if min_article <= num <= max_article:
            return article_number, warnings
        # If num exceeds max_article, it's likely a malformed sub-article
        # Fall through to candidate generation for dot insertion correction

    # Step 2.5: For hyphenated articles, check if base part should be corrected first
    # If the base would be corrected (e.g., "1237" → "123.7"), apply same correction to hyphenated
    if '-' in article_number:
        base_part = article_number.split('-')[0]
        hyphen_suffix = '-' + article_number.split('-')[1]

        if base_part.isdigit() and len(base_part) in (4, 5):
            # Check what the base would be corrected to
            base_candidates = _generate_dot_candidates(base_part)
            # Try to find a valid correction for the base
            for candidate in base_candidates:
                try:
                    parsed = _article_parser.parse(candidate)
                    base_num = parsed.to_float_for_comparison()
                    if min_article <= base_num <= max_article:
                        # Found valid correction for base, apply to hyphenated article
                        corrected = f"{candidate}{hyphen_suffix}"
                        return corrected, warnings
                except ValueError:
                    continue

        # If base is already within valid range, keep hyphenated format as-is
        if base_part.isdigit():
            base_num = int(base_part)
            if min_article <= base_num <= max_article:
                return article_number, warnings

    # Step 3: Generate all valid candidates by inserting dots
    candidates = _generate_dot_candidates(article_number)

    # Step 3.5: Check if original number should be preferred over transformations
    # Only keep original as-is if it's within STRICT valid range
    # Numbers exceeding max_article are likely sub-articles needing dot insertion
    # Example: 1061 should become 106.1 (sub-article of deleted article 106)
    try:
        original_parsed = _article_parser.parse(article_number)
        original_base = original_parsed.to_float_for_comparison()
        # Only prefer original if it's within actual valid range (not 10x expanded)
        if min_article <= original_base <= max_article:
            return article_number, warnings
        # If original exceeds max_article, it's likely a malformed sub-article
        # Fall through to candidate generation for dot insertion correction
    except ValueError:
        # Original number is invalid, continue with candidate validation
        pass

    # Step 4: Validate each candidate using ArticleNumberParser
    # Use previous article context to filter candidates when available
    if prev_article:
        try:
            prev_parsed = _article_parser.parse(prev_article)
            # Filter candidates using full ArticleNumber comparison (not base-only)
            # This correctly handles sub-articles like 306.1 vs 30.62
            context_filtered_candidates = []
            for candidate in candidates:
                try:
                    cand_parsed = _article_parser.parse(candidate)
                    # Only keep candidates that come after previous article
                    # Use full comparison: "306.1" > "273" is TRUE
                    if prev_parsed < cand_parsed:
                        # Also check base is within valid range
                        cand_base = cand_parsed.to_float_for_comparison()
                        if min_article <= cand_base <= max_article:
                            context_filtered_candidates.append((candidate, cand_parsed))
                except ValueError:
                    continue

            # If context filtering found candidates, use them
            if context_filtered_candidates:
                # Prefer candidates that maintain base consistency with prev
                # Example: prev=273, prefer 306.1 (base 306) over 30.62 (base 30)
                candidate, cand_parsed = context_filtered_candidates[0]
                if candidate != article_number:
                    warnings.append(f"Range-corrected: '{article_number}' → '{candidate}' (valid range: {min_article}-{max_article}, after prev={prev_article})")
                return candidate, warnings
        except ValueError:
            # Context parsing failed, fall through to non-context validation
            pass

    # Fallback: Non-context-aware range validation
    # Collect all valid candidates, then pick the one closest to range center
    # This prevents picking "10.51" (base=10) when "105.1" (base=105) is also valid
    valid_candidates = []
    range_center = (min_article + max_article) / 2

    for candidate in candidates:
        try:
            # Try to parse the candidate using ArticleNumberParser
            parsed = _article_parser.parse(candidate)
            base_num = parsed.to_float_for_comparison()

            # Check if the parsed base number is within valid range
            if min_article <= base_num <= max_article:
                valid_candidates.append((candidate, base_num))
        except ValueError:
            # Invalid format, try next candidate
            continue

    # If we have valid candidates, pick the one closest to range center
    if valid_candidates:
        # Sort by proximity to range center (prefer bases near middle of range)
        valid_candidates.sort(key=lambda x: abs(x[1] - range_center))
        best_candidate = valid_candidates[0][0]
        if best_candidate != article_number:
            warnings.append(f"Range-corrected: '{article_number}' → '{best_candidate}' (valid range: {min_article}-{max_article})")
        return best_candidate, warnings

    # Step 4.5: If context available, validate candidates against neighbors
    if prev_article and next_article:
        # Try to parse prev/next for full ArticleNumber comparison
        try:
            prev_parsed = _article_parser.parse(prev_article)
            next_parsed = _article_parser.parse(next_article)

            # Filter candidates that fit between prev and next using full comparison
            valid_candidates = []
            for candidate in candidates:
                try:
                    cand_parsed = _article_parser.parse(candidate)
                    # Use full ArticleNumber comparison: "306.1" < "306.2" < "306.3"
                    if prev_parsed < cand_parsed < next_parsed:
                        # Also verify base is within valid range
                        cand_base = cand_parsed.to_float_for_comparison()
                        if min_article <= cand_base <= max_article:
                            valid_candidates.append((candidate, cand_base))
                except ValueError:
                    continue

            # If we found context-valid candidates, pick the one closest to expected range
            if valid_candidates:
                # Sort by proximity to valid range center
                range_center = (min_article + max_article) / 2
                valid_candidates.sort(key=lambda x: abs(x[1] - range_center))
                best_candidate = valid_candidates[0][0]
                if best_candidate != article_number:
                    warnings.append(f"Context-aware range-corrected: '{article_number}' → '{best_candidate}' (prev={prev_article}, next={next_article})")
                return best_candidate, warnings
        except ValueError:
            # Context parsing failed, continue to range-based validation
            pass

    # Step 5: Could not auto-correct, return original with warning
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

    # Step 1: Handle HTML hierarchy encoding (multi-dot like "10.5.1" → "105.1")
    # Single-dot numbers like "6.1" are legitimate sub-articles - preserve them
    if '.' in article_number:
        dot_count = article_number.count('.')
        if dot_count >= 2:
            # Multi-dot = HTML hierarchy encoding
            # Format: "12.9.1" means article 129, part 1 (NOT chapter 12, section 9, part 1)
            # The first TWO numbers form the article number, the last is the subsection
            parts = article_number.split('.')

            # Check for hyphenated appendix (like "12.9.7-1")
            has_hyphen = '-' in parts[-1] if parts else False

            if dot_count == 2 and not has_hyphen:
                # "12.9.1" → "129.1" (merge first two parts, keep dot for last part)
                if all(p.isdigit() for p in parts):
                    merged_base = parts[0] + parts[1]  # "12" + "9" = "129"
                    article_number = f"{merged_base}.{parts[2]}"  # "129.1"
                    warnings.append(f"Converted hierarchy '{original}' to '{article_number}'")
            elif dot_count == 2 and has_hyphen:
                # "12.9.7-1" → "129.7-1" (merge first two parts, keep hyphen in last part)
                if parts[0].isdigit() and parts[1].isdigit():
                    merged_base = parts[0] + parts[1]
                    article_number = f"{merged_base}.{parts[2]}"  # "129.7-1"
                    warnings.append(f"Converted hierarchy '{original}' to '{article_number}'")
            else:
                # 4+ dots: convert all to dotless (old behavior for complex hierarchies)
                dotless = article_number.replace('.', '')
                if dotless.isdigit() and 2 < len(dotless) < 7:
                    warnings.append(f"Converted hierarchy '{original}' to '{dotless}'")
                    article_number = dotless
        # Single-dot articles (like "6.1") are legitimate sub-articles - keep as-is

    # Step 2: Handle hyphenated articles WITH dots (already correct) vs WITHOUT dots (need correction)
    # Hyphenated articles with dots like "52.1-1" are already correct - keep as-is
    # Hyphenated articles without dots like "521-1" need correction - continue to correction logic
    if '-' in article_number and '.' in article_number:
        # Already has both dot and hyphen, format is correct
        return article_number, warnings
    # Hyphenated articles without dots (e.g., "521-1") will proceed to correction logic below

    # Step 3: Try context-based correction (more accurate)
    if prev_article and next_article:
        corrected, context_warnings = try_context_correction(article_number, prev_article, next_article, code_id)
        if context_warnings:
            warnings.extend(context_warnings)
        # If context-based correction worked (changed the value), return it
        # Check this regardless of whether warnings were generated
        if corrected != original:
            return corrected, warnings
        elif corrected == article_number:
            # Context correction returned unchanged with no warnings
            # This could mean either: (a) it's valid, or (b) context was inconclusive
            # Fall through to consultant reference correction
            pass  # Continue to consultant reference correction

    # Step 3.5: Try consultant.ru reference correction (most accurate for ambiguous cases)
    # Uses consultant.ru's authoritative article numbers to disambiguate
    corrected, consultant_warnings = try_consultant_reference_correction(
        article_number, code_id, None, prev_article, next_article
    )
    if consultant_warnings:
        warnings.extend(consultant_warnings)
    if corrected:
        # Consultant reference found a match
        return corrected, warnings
    # If consultant correction returns None, fall through to range correction

    # Step 4: Fall back to range-based correction (with context if available)
    corrected, range_warnings = try_range_correction(article_number, code_id, prev_article, next_article)
    warnings.extend(range_warnings)

    return corrected, warnings


class BaseCodeImporter:
    """
    Import base legal code text from online sources.

    Supports:
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
        self._expected_paragraph_num = 1

    def _is_valid_article_content(
        self,
        text: str,
        source: str,
        article_number: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if text is valid article content or UI noise.

        Args:
            text: Text to validate
            source: Source domain ('kremlin', 'government', 'pravo')
            article_number: Optional article number for context-aware logging

        Returns:
            Tuple of (is_valid, filter_reason)
        """
        if not text or not text.strip():
            return False, "empty_text"

        text = text.strip()

        # Length checks
        if len(text) < 10:
            return False, f"too_short_{len(text)}_chars"

        if len(text) > 5000:
            return False, f"too_long_{len(text)}_chars"

        # Section/chapter headers (already filtered in existing code)
        if text.startswith(("Раздел", "Глава", "Подраздел")):
            return False, "section_header"

        # Section/subsection headers that are structural titles, not content
        # 1. Section symbol headers (e.g., "§ 7. Некоммерческие унитарные организации")
        if re.match(r"^§\s+\d+\.?\s*[А-Яа-яЁёA-Za-z].*", text):
            return False, "section_symbol_header"

        # 2. Numbered section titles followed by parenthetical amendment note
        # Only filter SHORT titles (under 100 chars) to avoid filtering real article content
        # Real article content like part 5 of article 1.3 can be 300+ chars with amendment notes
        if re.match(r"^\d+\.\s+[А-Яа-яЁё].*\s*\(.*(?:дополнение| редакция| редакции| утратил).+\)", text, re.IGNORECASE):
            if len(text) < 100:
                return False, "subsection_title_with_amendment"

        # First, clean text by removing UI noise that's embedded within content
        # This handles cases where UI elements are concatenated with legal text
        ui_substitution_patterns = [
            # Pagination buttons embedded in text
            (r"Показать предыдущую страницу документа", ""),
            (r"Показать следующую страницу документа", ""),
            (r"Show previous page", ""),
            (r"Show next page", ""),
            # Share buttons embedded in text
            (r"Поделиться\s*", ""),
            (r"Подписаться\s*", ""),
            # Other common embedded UI
            (r"Версия официального сайта для мобильных устройств\s*", ""),
            (r"Текст\s*", ""),
            # NEW: Concatenated social media names (no spaces)
            (r"ВКонтактеTelegramОдноклассникиVKRutubeYouTube", ""),
            (r"ВКонтакте\s*Telegram\s*Одноклассники", ""),
            (r"VK\s*OK\s*Rutube", ""),
            # NEW: Concatenated navigation elements
            (r"СобытияСтруктураВидео\s*и\s*фотоДокументыКонтактыПоиск", ""),
            (r"Официальные\s+сетевые\s+ресурсы", ""),
            (r"Президент\s+России", ""),
            # NEW: Concatenated share buttons
            (r"Скопировать\s+ссылкуПереслать\s+на\s+почтуРаспечатать", ""),
            (r"Переслать\s+материал\s+на\s+почтуПросмотр\s+отправляемого\s+сообщения", ""),
            # NEW: Footer patterns
            (r"Администрация\s+Президента\s+России\s*\d{4}\s+год", ""),
            (r"Официальный\s+сайт\s+президента\s+России", ""),
            (r"Правовая\s+и\s+техническая\s+информация", ""),
            (r"О\s+порталеОб\s+использовании\s+информации\s+сайта", ""),
            # NEW: Government.ru specific patterns
            (r"Email\s+адресата\*Введите\s+корректый\s+EmailТекст\s+сообщенияGovernment\.ru:", ""),
            (r"Введите\s+корректый\s+Email", ""),
            (r"Текст\s+сообщенияGovernment\.ru:", ""),
            (r"Government\.ru:Отправить", ""),
            (r"СпасибоВниманиеТекст\s+сообщенияGovernment\.ru:", ""),
            (r"Спасибо\s*Внимание", ""),
            # NEW: Government.ru navigation
            (r"Правительство\s+РоссииПредседатель\s+ПравительстваВице-премьерыМинистерства\s+и\s+ведомства", ""),
            (r"Правительство\s+России", ""),
            (r"Председатель\s+Правительства", ""),
            (r"Вице-премьеры", ""),
            (r"Министерства\s+и\s+ведомства", ""),
            (r"МинистрыСоветы\s+и\s+комиссии", ""),
            (r"По\s+регионамОбращения", ""),
            (r"ГосуслугиРабота\s+Правительства", ""),
            (r"ДемографияЗдоровьеОбразованиеКультураОбществоГосударствоЗанятость\s+и\s+труд", ""),
            (r"Технологическое\s+развитиеЭкономика\.\s+РегулированиеФинансыСоциальные\s+услугиЭкологияЖильё\s+и\s+городаТранспорт\s+и\s+связьЭнергетикаПромышленностьСельское\s+хозяйствоРегиональное\s+развитиеДальний\s+ВостокРоссия\s+и\s+мирБезопасностьПраво\s+и\s+юстиция", ""),
            # NEW: Government.ru document types
            (r"СтратегииГосударственные\s+программыНациональные\s+проектыРазвернуть", ""),
            (r"РазвернутьДокументыИзбранные\s+документы\s+со\s+справками\s+к\s+ним", ""),
            (r"Поиск\s+по\s+всем\s+документамВид\s+документаПостановление\s+Правительства\s+Российской\s+ФедерацииРаспоряжение\s+Правительства\s+Российской\s+ФедерацииРаспоряжение\s+Президента\s+Российской\s+ФедерацииУказ\s+Президента\s+Российской\s+ФедерацииФедеральный\s+законФедеральный\s+конституционный\s+законКодекс", ""),
            (r"Вид\s+документаПостановление\s+Правительства\s+Российской\s+ФедерацииРаспоряжение\s+Правительства\s+Российской\s+Федерации", ""),
            (r"НомерЗаголовок\s+или\s+текст\s+документаДата\s+подписанияНайти", ""),
            (r"Заголовок\s+или\s+текст\s+документа", ""),
            (r"Дата\s+подписанияНайти", ""),
            (r"Поиск\s+по\s+документамстраница", ""),
            (r"Показать\s+еще", ""),
            # NEW: Font size controls
            (r"Маленький\s+размер\s+шрифтаНормальный\s+размер\s+шрифтаБольшой\s+размер\s+шрифтаВключить/выключить\s+отображение\s+изображенийВклВыкл", ""),
            (r"Маленький\s+размер\s+шрифта", ""),
            (r"Нормальный\s+размер\s+шрифта", ""),
            (r"Большой\s+размер\s+шрифта", ""),
            (r"Включить/выключить\s+отображение\s+изображений", ""),
            # NEW: Browser links
            (r"ChromeFirefoxInternet\s+ExplorerOperaSafari", ""),
            (r"Вы\s+пользуетесь\s+устаревшей\s+версией\s+браузера", ""),
            (r"Внимание!\s+Вы\s+используете\s+устаревшую\s+версию\s+браузера", ""),
            # NEW: Blog embed
            (r"Код\s+для\s+вставки\s+в\s+блогСкопировать\s+в\s+буфер", ""),
            (r"Следующая\s+новость", ""),
            (r"Предыдущая\s+новость", ""),
        ]

        original_text = text
        for pattern, replacement in ui_substitution_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Log if text was cleaned
        if text != original_text:
            logger.debug(
                f"[{source}] Cleaned embedded UI from '{original_text[:50]}...' "
                f"(article: {article_number})"
            )
            # After cleaning, check if there's still meaningful content
            if len(text.strip()) < 10:
                return False, "cleaned_too_short"

        # UI noise patterns to filter (standalone UI elements)
        ui_patterns = [
            # Social media and sharing
            r"^Поделиться$",
            r"^(ВКонтакте|Telegram|Одноклассники|VK|OK|Rutube|YouTube)$",
            r"^Telegram-канал$",
            r"^Скопировать ссылку$",
            r"^Переслать на почту$",
            r"^Распечатать$",
            # Links and navigation
            r"^Прямая ссылка на материал",
            r"^https?://\S+$",
            r"или по банку документов",
            # Navigation items
            r"^(События|Структура|Видео и фото|Документы|Контакты|Поиск)$",
            r"^(О портале|О сайте|Карта сайта)$",
            r"^Найти документ$",
            r"^Официальные сетевые ресурсы$",
            r"Информационные ресурсы",
            # Search/form elements
            r"^(Название документа или его номер|Текст в документе)$",
            r"^Вид документаВсе$",
            r"^(Указ|Распоряжение|Федеральный закон|Федеральный конституционный закон|Послание|Закон Российской Федерации о поправке к Конституции Российской Федерации|Кодекс)$",
            r"^Дата вступления в силу",
            r"^или дата принятия",
            r"^(Введите запрос|Искать на сайте|Найти)$",
            r"^Официальный портал правовой информации",
            # Footer and administrative
            r"^\d{4}\s+год\.?$",
            r"^Администрация Президента России",
            r"^Официальный сайт президента России",
            r"Для СМИ$",
            r"Специальная версия для людей с ограниченными возможностями",
            r"^Правовая и техническая информация$",
            # Footer links
            r"^(Конституция России|Государственная символика)$",
            r"Обратиться к Президенту",
            r"Президент России[—-]гражданам школьного возраста",
            r"Виртуальный тур поКремлю",
            r"Владимир Путин[—-]личный сайт",
            r"Дикая природа России",
            r"Путин\. \d+ лет",
            r"^Написать в редакцию$",
            # License
            r"Creative Commons Attribution \d\.\d",
            r"Все материалы сайта доступны по лицензии",
            # Form elements
            r"^Электронная почта адресата$",
            r"^Отправить$",
            # General UI labels
            r"^Текст$",
            # Pagination buttons
            r"^(Показать предыдущую страницу документа|Показать следующую страницу документа)$",
            r"^(Show previous page|Show next page)$",
            # NEW: Multi-line concatenated UI
            r"^Просмотр отправляемого сообщения$",
            r"^Электронная почта адресатаОтправить$",
            r"^Переслать материал на почтуПросмотр отправляемого сообщения$",
            # NEW: Government.ru specific patterns
            r"^Email\s+адресата\*",
            r"^Текст\s+сообщенияGovernment\.ru:$",
            r"^Government\.ru:Отправить$",
            r"^СпасибоВнимание",
            r"^Правительство\s+РоссииПредседатель",
            r"^СтратегииГосударственные\s+программыНациональные\s+проекты",
            r"^РазвернутьДокументыИзбранные",
            r"^Вид\s+документаПостановление\s+Правительства",
            r"^НомерЗаголовок\s+или\s+текст",
            r"^Поиск\s+по\s+документамстраница",
            r"^Маленький\s+размер\s+шрифтаНормальный",
            r"^ChromeFirefoxInternet\s+Explorer",
            r"^Код\s+для\s+вставки\s+в\s+блог",
            r"^Вы\s+пользуетесь\s+устаревшей",
            r"^Следующая\s+новость$",
            r"^Предыдущая\s+новость$",
            # NEW: Concatenated document titles (government.ru repeats these)
            r"^\d{1,2}\s+дня\s+прошлый\s+день\d{1,2}\s+дня\s+назад",
            r"^\d{1,2}\s+дня\s+прошлый\s+день",
        ]

        # Now check against standalone UI patterns (text that's entirely UI noise)
        for pattern in ui_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(
                    f"[{source}] Filtered '{text[:50]}...' "
                    f"(article: {article_number}, pattern: {pattern})"
                )
                return False, f"ui_pattern_{pattern[:20]}"

        # Character ratio checks
        total = len(text)
        digit_ratio = sum(c.isdigit() for c in text) / total if total > 0 else 0

        # High digit ratio (>40%) suggests encoded data
        if digit_ratio > 0.4:
            return False, f"high_digit_ratio_{digit_ratio:.2f}"

        # Passed all checks - this is valid content
        return True, None


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

        while True:
            url = f"http://www.kremlin.ru/acts/bank/{bank_id}/page/{page_num}"
            try:
                logger.info(f"Fetching page {page_num}: {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"

                # Always save the page - continuation content may exist without "Статья" header
                all_pages.append(response.text)

                page_num += 1

                # Sleep to avoid rate limiting
                time.sleep(config.import_request_delay)

                # Safety limit to prevent infinite loops (now configurable)
                if page_num > config.import_max_pages:
                    logger.warning(f"Reached page limit ({config.import_max_pages}), stopping pagination")
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
        # Handle multiple pages with continuation tracking
        if isinstance(html, list):
            # Phase 1: Parse all pages to get raw articles (no validation yet)
            all_raw_articles = []
            current_article = None
            current_paragraphs = []

            for i, page_html in enumerate(html):
                raw_articles, current_article, current_paragraphs = self._parse_raw_articles_from_page(
                    page_html, code_id, current_article, current_paragraphs
                )
                all_raw_articles.extend(raw_articles)

            # Flush final article if exists
            if current_article and current_paragraphs:
                current_article["article_text"] = "\n\n".join(current_paragraphs)
                all_raw_articles.append(current_article)

            logger.info(f"Parsed {len(all_raw_articles)} raw articles from {len(html)} pages")

            # Phase 2: Validate all articles together with full context
            articles = []
            for i, raw_article in enumerate(all_raw_articles):
                raw_number = raw_article["article_number"]
                # Use corrected previous article for context (not raw) - this allows proper sub-article detection
                prev_article = articles[i - 1]["article_number"] if i > 0 else None
                # Use raw next article for context (not yet corrected)
                next_article = all_raw_articles[i + 1]["article_number"] if i < len(all_raw_articles) - 1 else None

                # Log what we're parsing (verbose mode shows raw number and context)
                logger.debug(f"[{code_id}] Parsing article: '{raw_number}' (prev={prev_article}, next={next_article})")

                # Validate with full context
                corrected_number, warnings = validate_and_correct_article_number(
                    raw_number, code_id, prev_article, next_article
                )

                # Log final result (verbose mode shows correction or validation)
                if corrected_number == raw_number:
                    logger.debug(f"[{code_id}] Article '{raw_number}' validated - no change needed")
                else:
                    logger.debug(f"[{code_id}] Article '{raw_number}' corrected to '{corrected_number}'")

                for warning in warnings:
                    logger.warning(f"[{code_id}] {warning}")

                # Update title if article_number changed
                article_title = raw_article["article_title"]
                if corrected_number != raw_number:
                    # Replace old article number in title with corrected one
                    old_num_pattern = re.escape(raw_number)
                    article_title = re.sub(
                        f"Статья\\s+{old_num_pattern}",
                        f"Статья {corrected_number}",
                        article_title,
                        flags=re.IGNORECASE
                    )

                articles.append({
                    **raw_article,
                    "article_number": corrected_number,
                    "article_title": article_title,
                })

            # Verbose mode: Summary of all article numbers (initial and saved)
            logger.debug(f"[{code_id}] Article numbers: initial → saved")
            for raw_article, final_article in zip(all_raw_articles, articles):
                raw_num = raw_article["article_number"]
                final_num = final_article["article_number"]
                if raw_num != final_num:
                    logger.debug(f"[{code_id}]   '{raw_num}' → '{final_num}'")
                else:
                    logger.debug(f"[{code_id}]   '{raw_num}' (no change)")

            logger.info(f"Validated to {len(articles)} articles from kremlin.ru")
            return {
                "code_id": code_id,
                "articles": articles,
                "source": "kremlin.ru",
            }
        else:
            # Single page - just get the result, ignore state
            result, _, _ = self._parse_single_kremlin_page(html, code_id)
            return result

    def _parse_raw_articles_from_page(
        self,
        html: str,
        code_id: str,
        current_article: Optional[Dict] = None,
        current_paragraphs: Optional[List] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict], Optional[List]]:
        """
        Parse a single kremlin.ru HTML page to extract RAW articles (no validation).

        This is similar to _parse_single_kremlin_page but does NOT validate article numbers.
        It only extracts raw articles from HTML, leaving validation for a later step.

        Supports continuation tracking across pages - accepts and returns
        current_article and current_paragraphs state.

        Args:
            html: HTML content
            code_id: Code identifier
            current_article: Previous page's article (for continuation)
            current_paragraphs: Previous page's paragraphs (for continuation)

        Returns:
            Tuple of (raw_articles_list, current_article, current_paragraphs)
        """
        soup = BeautifulSoup(html, "html.parser")

        raw_articles = []
        # Use passed state or initialize fresh
        if current_article is None:
            current_article = None
        if current_paragraphs is None:
            current_paragraphs = []

        # Track processed elements to avoid processing nested elements multiple times
        processed = set()

        # CRITICAL: kremlin.ru has content in <div class="reader_act_body">
        # We must ONLY process elements within these divs to avoid picking up UI noise
        act_body_divs = soup.find_all("div", class_="reader_act_body")

        if not act_body_divs:
            logger.warning(f"[{code_id}] No reader_act_body divs found in HTML")
            # Return empty list with current state preserved
            return [], current_article, current_paragraphs

        # Find all text elements within reader_act_body divs
        # Only process leaf elements (not nested within other processed elements)
        for act_body in act_body_divs:
            for element in act_body.find_all(["h4", "p", "div"]):
                # Skip if this element or any of its parents have been processed
                should_skip = False
                for parent in element.parents:
                    if parent in processed:
                        should_skip = True
                        break
                if should_skip:
                    continue

                # Get text - use .string for elements with only direct text
                # This prevents concatenation from nested elements
                if element.string and element.string.strip():
                    text = element.string.strip()
                else:
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
                    # Reset paragraph counter for new article
                    self._expected_paragraph_num = 1
                    processed.add(element)

                elif current_article and text:
                    # Check if this is a numbered paragraph (starts with number and period)
                    paragraph_match = re.match(r"^(\d+)\.\s*(.+)$", text)

                    if paragraph_match:
                        para_num = int(paragraph_match.group(1))

                        # FIRST: Check if this is a subsection title with amendment note
                        # Amendment pattern takes precedence over sequential validation
                        # This catches ALL three cases regardless of number:
                        # - Case 1: "1. ..." after "4." (para_num < expected)
                        # - Case 2: "4. ..." after "4." (para_num < expected, same as previous)
                        # - Case 3: "5. ..." when expected=5 (para_num == expected)
                        if re.search(
                            r'\(.*(?:дополнение|редакция|редакции|утратил|Наименование|Дополнение).+\)',
                            text,
                            re.IGNORECASE
                        ):
                            logger.debug(
                                f"[kremlin] Filtered subsection title with amendment: '{text[:50]}...'"
                            )
                            processed.add(element)
                            continue

                        # THEN: Do sequential validation
                        # Check if this is the expected next number or a valid sub-item
                        if para_num < self._expected_paragraph_num:
                            # Number is less than expected - could be duplicate or reordering
                            # Accept it but don't change expected counter
                            logger.debug(
                                f"[kremlin] Paragraph {para_num} < expected {self._expected_paragraph_num}, accepting"
                            )
                            current_paragraphs.append(text)
                        elif para_num == self._expected_paragraph_num:
                            # Exact match - perfect sequence
                            current_paragraphs.append(text)
                            self._expected_paragraph_num = para_num + 1
                        elif para_num > self._expected_paragraph_num:
                            # Number is higher than expected - check if it's a valid sub-item
                            # Sub-items are encoded as: base * 10 + sub_num (e.g., 2.1 = 21, 4.2 = 42)
                            # The sub-item could be of the expected number OR the previous base number
                            # Example: after 2 (expected=3), we might see 21 (sub-item of 2)

                            # Check if it's a sub-item of the expected number
                            expected_base = self._expected_paragraph_num * 10
                            if para_num >= expected_base and para_num < expected_base + 10:
                                # Valid sub-item of expected number
                                logger.debug(
                                    f"[kremlin] Sub-item detected: {para_num} (expected {self._expected_paragraph_num}, representing {self._expected_paragraph_num}.{para_num % 10})"
                                )
                                current_paragraphs.append(text)
                                # Don't update expected counter - main sequence continues
                            # Check if it's a sub-item of the previous base number (expected - 1)
                            elif self._expected_paragraph_num > 1:
                                prev_base = (self._expected_paragraph_num - 1) * 10
                                if para_num >= prev_base and para_num < prev_base + 10:
                                    # Valid sub-item of previous base number
                                    logger.debug(
                                        f"[kremlin] Sub-item detected: {para_num} (of prev {self._expected_paragraph_num - 1}, representing {self._expected_paragraph_num - 1}.{para_num % 10})"
                                    )
                                    current_paragraphs.append(text)
                                    # Don't update expected counter - main sequence continues
                                else:
                                    # Not a sub-item - section header
                                    logger.debug(
                                        f"[kremlin] Filtered section header '{text[:50]}...' "
                                        f"(got {para_num}, expected {self._expected_paragraph_num})"
                                    )
                                    processed.add(element)
                                    continue
                            else:
                                # Not a sub-item - section header
                                logger.debug(
                                    f"[kremlin] Filtered section header '{text[:50]}...' "
                                    f"(got {para_num}, expected {self._expected_paragraph_num})"
                                )
                                processed.add(element)
                                continue
                    else:
                        # Use helper function to filter UI noise
                        is_valid, filter_reason = self._is_valid_article_content(
                            text, "kremlin", current_article.get("article_number")
                        )
                        if is_valid:
                            current_paragraphs.append(text)

        # Return RAW articles (no validation yet) and current state
        return raw_articles, current_article, current_paragraphs

    def _parse_single_kremlin_page(
        self,
        html: str,
        code_id: str,
        current_article: Optional[Dict] = None,
        current_paragraphs: Optional[List] = None
    ) -> Tuple[Dict[str, Any], Optional[Dict], Optional[List]]:
        """
        Parse a single kremlin.ru HTML page to extract articles.

        Supports continuation tracking across pages - accepts and returns
        current_article and current_paragraphs state.
        Only processes content within <div class="reader_act_body"> elements.

        Args:
            html: HTML content
            code_id: Code identifier
            current_article: Previous page's article (for continuation)
            current_paragraphs: Previous page's paragraphs (for continuation)

        Returns:
            Tuple of (result_dict, current_article, current_paragraphs)
        """
        soup = BeautifulSoup(html, "html.parser")

        raw_articles = []
        # Use passed state or initialize fresh
        if current_article is None:
            current_article = None
        if current_paragraphs is None:
            current_paragraphs = []

        # Track processed elements to avoid processing nested elements multiple times
        processed = set()

        # CRITICAL: kremlin.ru has content in <div class="reader_act_body">
        # We must ONLY process elements within these divs to avoid picking up UI noise
        act_body_divs = soup.find_all("div", class_="reader_act_body")

        if not act_body_divs:
            logger.warning(f"[{code_id}] No reader_act_body divs found in HTML")
            # Return empty result with current state preserved
            return {
                "code_id": code_id,
                "articles": [],
                "source": "kremlin.ru",
            }, current_article, current_paragraphs

        # Find all text elements within reader_act_body divs
        # Only process leaf elements (not nested within other processed elements)
        for act_body in act_body_divs:
            for element in act_body.find_all(["h4", "p", "div"]):
                # Skip if this element or any of its parents have been processed
                should_skip = False
                for parent in element.parents:
                    if parent in processed:
                        should_skip = True
                        break
                if should_skip:
                    continue

                # Get text - use .string for elements with only direct text
                # This prevents concatenation from nested elements
                if element.string and element.string.strip():
                    text = element.string.strip()
                else:
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
                    # Reset paragraph counter for new article
                    self._expected_paragraph_num = 1
                    processed.add(element)

                elif current_article and text:
                    # Check if this is a numbered paragraph (starts with number and period)
                    paragraph_match = re.match(r"^(\d+)\.\s*(.+)$", text)

                    if paragraph_match:
                        para_num = int(paragraph_match.group(1))

                        # FIRST: Check if this is a subsection title with amendment note
                        # Amendment pattern takes precedence over sequential validation
                        # This catches ALL three cases regardless of number:
                        # - Case 1: "1. ..." after "4." (para_num < expected)
                        # - Case 2: "4. ..." after "4." (para_num < expected, same as previous)
                        # - Case 3: "5. ..." when expected=5 (para_num == expected)
                        if re.search(
                            r'\(.*(?:дополнение|редакция|редакции|утратил|Наименование|Дополнение).+\)',
                            text,
                            re.IGNORECASE
                        ):
                            logger.debug(
                                f"[kremlin] Filtered subsection title with amendment: '{text[:50]}...'"
                            )
                            processed.add(element)
                            continue

                        # THEN: Do sequential validation
                        # Check if this is the expected next number or a valid sub-item
                        if para_num < self._expected_paragraph_num:
                            # Number is less than expected - could be duplicate or reordering
                            # Accept it but don't change expected counter
                            logger.debug(
                                f"[kremlin] Paragraph {para_num} < expected {self._expected_paragraph_num}, accepting"
                            )
                            current_paragraphs.append(text)
                        elif para_num == self._expected_paragraph_num:
                            # Exact match - perfect sequence
                            current_paragraphs.append(text)
                            self._expected_paragraph_num = para_num + 1
                        elif para_num > self._expected_paragraph_num:
                            # Number is higher than expected - check if it's a valid sub-item
                            # Sub-items are encoded as: base * 10 + sub_num (e.g., 2.1 = 21, 4.2 = 42)
                            # The sub-item could be of the expected number OR the previous base number
                            # Example: after 2 (expected=3), we might see 21 (sub-item of 2)

                            # Check if it's a sub-item of the expected number
                            expected_base = self._expected_paragraph_num * 10
                            if para_num >= expected_base and para_num < expected_base + 10:
                                # Valid sub-item of expected number
                                logger.debug(
                                    f"[kremlin] Sub-item detected: {para_num} (expected {self._expected_paragraph_num}, representing {self._expected_paragraph_num}.{para_num % 10})"
                                )
                                current_paragraphs.append(text)
                                # Don't update expected counter - main sequence continues
                            # Check if it's a sub-item of the previous base number (expected - 1)
                            elif self._expected_paragraph_num > 1:
                                prev_base = (self._expected_paragraph_num - 1) * 10
                                if para_num >= prev_base and para_num < prev_base + 10:
                                    # Valid sub-item of previous base number
                                    logger.debug(
                                        f"[kremlin] Sub-item detected: {para_num} (of prev {self._expected_paragraph_num - 1}, representing {self._expected_paragraph_num - 1}.{para_num % 10})"
                                    )
                                    current_paragraphs.append(text)
                                    # Don't update expected counter - main sequence continues
                                else:
                                    # Not a sub-item - section header
                                    logger.debug(
                                        f"[kremlin] Filtered section header '{text[:50]}...' "
                                        f"(got {para_num}, expected {self._expected_paragraph_num})"
                                    )
                                    processed.add(element)
                                    continue
                            else:
                                # Not a sub-item - section header
                                logger.debug(
                                    f"[kremlin] Filtered section header '{text[:50]}...' "
                                    f"(got {para_num}, expected {self._expected_paragraph_num})"
                                )
                                processed.add(element)
                                continue
                    else:
                        # Use helper function to filter UI noise
                        is_valid, filter_reason = self._is_valid_article_content(
                            text, "kremlin", current_article.get("article_number")
                        )
                        if is_valid:
                            current_paragraphs.append(text)

        # Return completed articles and current state (don't flush yet - caller handles that)
        articles = []
        for raw_article in raw_articles:
            # Validate article number
            raw_number = raw_article["article_number"]

            # Get context for validation
            prev_article = raw_articles[raw_articles.index(raw_article) - 1]["article_number"] if raw_articles.index(raw_article) > 0 else None
            next_article = raw_articles[raw_articles.index(raw_article) + 1]["article_number"] if raw_articles.index(raw_article) < len(raw_articles) - 1 else None

            # Log what we're parsing (verbose mode shows raw number and context)
            logger.debug(f"[{code_id}] Parsing article: '{raw_number}' (prev={prev_article}, next={next_article})")

            # Validate with hybrid approach
            corrected_number, warnings = validate_and_correct_article_number(
                raw_number, code_id, prev_article, next_article
            )

            # Log final result (verbose mode shows correction or validation)
            if corrected_number == raw_number:
                logger.debug(f"[{code_id}] Article '{raw_number}' validated - no change needed")
            else:
                logger.debug(f"[{code_id}] Article '{raw_number}' corrected to '{corrected_number}'")

            for warning in warnings:
                logger.warning(f"[{code_id}] {warning}")

            # Update title if article_number changed
            article_title = raw_article["article_title"]
            if corrected_number != raw_number:
                # Replace old article number in title with corrected one
                old_num_pattern = re.escape(raw_number)
                article_title = re.sub(
                    f"Статья\\s+{old_num_pattern}",
                    f"Статья {corrected_number}",
                    article_title,
                    flags=re.IGNORECASE
                )

            articles.append({
                **raw_article,
                "article_number": corrected_number,
                "article_title": article_title,
            })

        # Verbose mode: Summary of all article numbers (initial and saved)
        logger.debug(f"[{code_id}] Article numbers: initial → saved")
        for raw_article, final_article in zip(raw_articles, articles):
            raw_num = raw_article["article_number"]
            final_num = final_article["article_number"]
            if raw_num != final_num:
                logger.debug(f"[{code_id}]   '{raw_num}' → '{final_num}'")
            else:
                logger.debug(f"[{code_id}]   '{raw_num}' (no change)")

        return {
            "code_id": code_id,
            "articles": articles,
            "source": "kremlin.ru",
        }, current_article, current_paragraphs

    def import_code(self, code_id: str, source: str = "auto") -> Dict[str, Any]:
        """
        Import a legal code from specified source.

        Automatically falls back to alternative sources if the primary is unavailable:
        - kremlin (official) -> pravo (official) -> government (official)

        Args:
            code_id: Code identifier (e.g., 'TK_RF')
            source: Source to import from ('auto', 'kremlin', 'pravo', 'government')

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
                # Allow up to 10x max (handles 4-digit articles, appendices, parts)
                # Some codes have articles beyond the base range (e.g., GK_RF has 1237, 12310-12320)
                if num > max_article * 10:
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
                                # Validate article count
                                count_warnings = validate_article_count(code_id, len(articles))
                                for warning in count_warnings:
                                    logger.warning(f"[{code_id}] {warning}")

                                # Merge source into metadata
                                save_metadata = {**metadata, "source": parsed.get("source", "kremlin.ru")}
                                saved = self.save_base_articles(code_id, articles, save_metadata)
                                return {
                                    "code_id": code_id,
                                    "status": "success",
                                    "pages_fetched": len(html_pages),
                                    "articles_found": len(articles),
                                    "articles_processed": len(articles),
                                    "articles_saved": saved,
                                    "source": parsed.get("source", "kremlin"),
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
                                # Validate article count
                                count_warnings = validate_article_count(code_id, len(articles))
                                for warning in count_warnings:
                                    logger.warning(f"[{code_id}] {warning}")

                                # Merge source into metadata
                                save_metadata = {**metadata, "source": parsed.get("source", "pravo.gov.ru")}
                                saved = self.save_base_articles(code_id, articles, save_metadata)
                                return {
                                    "code_id": code_id,
                                    "status": "success",
                                    "articles_found": len(articles),
                                    "articles_processed": len(articles),
                                    "articles_saved": saved,
                                    "source": parsed.get("source", "pravo"),
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
                                # Validate article count
                                count_warnings = validate_article_count(code_id, len(articles))
                                for warning in count_warnings:
                                    logger.warning(f"[{code_id}] {warning}")

                                # Merge source into metadata
                                save_metadata = {**metadata, "source": parsed.get("source", "government.ru")}
                                saved = self.save_base_articles(code_id, articles, save_metadata)
                                return {
                                    "code_id": code_id,
                                    "status": "success",
                                    "pages_fetched": len(html_pages),
                                    "articles_found": len(articles),
                                    "articles_processed": len(articles),
                                    "articles_saved": saved,
                                    "source": parsed.get("source", "government"),
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
                            save_metadata = {**metadata, "source": parsed.get("source", "pravo.gov.ru")}
                            saved = self.save_base_articles(code_id, articles, save_metadata)
                            return {
                                "code_id": code_id,
                                "status": "success",
                                "articles_found": len(articles),
                                "articles_processed": len(articles),
                                "articles_saved": saved,
                                "source": parsed.get("source", "pravo"),
                            }

                elif src_name == "kremlin":
                    logger.info(f"Fetching Constitution from kremlin.ru: {src_value}")
                    response = self.session.get(src_value, timeout=self.timeout)
                    response.raise_for_status()
                    response.encoding = "utf-8"

                    parsed = self.parse_constitution(response.text, code_id)
                    articles = parsed.get("articles", [])
                    if articles:
                        save_metadata = {**metadata, "source": parsed.get("source", "kremlin.ru")}
                        saved = self.save_base_articles(code_id, articles, save_metadata)
                        return {
                            "code_id": code_id,
                            "status": "success",
                            "articles_found": len(articles),
                            "articles_processed": len(articles),
                            "articles_saved": saved,
                            "source": parsed.get("source", "kremlin"),
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

        # Track processed elements to avoid processing nested elements multiple times
        processed = set()

        # Pravo.gov.ru uses article headers like "Статья 1. Title"
        # Look for article patterns - collect raw first
        for element in soup.find_all(["h3", "h4", "p", "div"]):
            # Skip if this element or any of its parents have been processed
            should_skip = False
            for parent in element.parents:
                if parent in processed:
                    should_skip = True
                    break
            if should_skip:
                continue

            # Get text - use .string for elements with only direct text
            if element.string and element.string.strip():
                text = element.string.strip()
            else:
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
                    if para_text:
                        # Use helper function to filter UI noise
                        is_valid, filter_reason = self._is_valid_article_content(
                            para_text, "pravo", article_number
                        )
                        if is_valid:
                            content_paragraphs.append(para_text)
                    current_element = current_element.find_next_sibling(["p", "div"])

                raw_articles.append(
                    {
                        "article_number": article_number,
                        "article_title": article_title,
                        "article_text": "\n\n".join(content_paragraphs),
                    }
                )
                processed.add(element)

        logger.info(f"Found {len(raw_articles)} raw articles from pravo.gov.ru")

        # NOW validate and correct article numbers with context
        articles = []
        for i, raw_article in enumerate(raw_articles):
            raw_number = raw_article["article_number"]

            # Get context for validation
            # Use corrected previous article for context (not raw) - this allows proper sub-article detection
            prev_article = articles[i - 1]["article_number"] if i > 0 else None
            # Use raw next article for context (not yet corrected)
            next_article = raw_articles[i + 1]["article_number"] if i < len(raw_articles) - 1 else None

            # Log what we're parsing (verbose mode shows raw number and context)
            logger.debug(f"[{code_id}] Parsing article: '{raw_number}' (prev={prev_article}, next={next_article})")

            # Validate with hybrid approach
            corrected_number, warnings = validate_and_correct_article_number(
                raw_number, code_id, prev_article, next_article
            )

            # Log final result (verbose mode shows correction or validation)
            if corrected_number == raw_number:
                logger.debug(f"[{code_id}] Article '{raw_number}' validated - no change needed")
            else:
                logger.debug(f"[{code_id}] Article '{raw_number}' corrected to '{corrected_number}'")

            for warning in warnings:
                logger.warning(f"[{code_id}] {warning}")

            # Update title if article_number changed
            article_title = raw_article["article_title"]
            if corrected_number != raw_number:
                # Replace old article number in title with corrected one
                old_num_pattern = re.escape(raw_number)
                article_title = re.sub(
                    f"Статья\\s+{old_num_pattern}",
                    f"Статья {corrected_number}",
                    article_title,
                    flags=re.IGNORECASE
                )

            articles.append({
                **raw_article,
                "article_number": corrected_number,
                "article_title": article_title,
            })

        logger.info(f"Validated to {len(articles)} articles from pravo.gov.ru")

        # Verbose mode: Summary of all article numbers (initial and saved)
        logger.debug(f"[{code_id}] Article numbers: initial → saved")
        for raw_article, final_article in zip(raw_articles, articles):
            raw_num = raw_article["article_number"]
            final_num = final_article["article_number"]
            if raw_num != final_num:
                logger.debug(f"[{code_id}]   '{raw_num}' → '{final_num}'")
            else:
                logger.debug(f"[{code_id}]   '{raw_num}' (no change)")

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

        while True:
            page_url = f"{url}?page={page_num}" if page_num > 1 else url
            try:
                logger.info(f"Fetching page {page_num}: {page_url}")
                response = self.session.get(page_url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"

                # Always save the page - continuation content may exist without "Статья" header
                all_pages.append(response.text)

                page_num += 1

                # Sleep to avoid rate limiting (government.ru is sensitive)
                time.sleep(config.import_request_delay)

                # Safety limit to prevent infinite loops (now configurable)
                if page_num > config.import_max_pages:
                    logger.warning(f"Reached page limit ({config.import_max_pages}), stopping pagination")
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

        Uses two-phase parsing for multi-page documents:
        1. Extract all raw articles from all pages
        2. Validate all articles together with full context (fixes issue #23)

        Args:
            html: HTML content (single page string or list of pages)
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        # Handle multiple pages - two-phase approach to maintain context across pages
        if isinstance(html, list):
            # Phase 1: Extract all raw articles from all pages (without validation)
            all_raw_articles = []
            for i, page_html in enumerate(html):
                raw_articles = self._extract_raw_articles_from_government_page(page_html, code_id)
                all_raw_articles.extend(raw_articles)
            logger.info(f"Extracted {len(all_raw_articles)} raw articles from {len(html)} pages")

            # Phase 2: Validate all articles together with full context
            # This ensures articles like "231" at the start of page 2 have prev="23" from page 1
            validated_articles = self._validate_and_correct_articles(all_raw_articles, code_id)

            return {
                "code_id": code_id,
                "articles": validated_articles,
                "source": "government.ru",
            }
        else:
            # Single page - use existing method
            return self._parse_single_government_page(html, code_id)

    def _extract_raw_articles_from_government_page(self, html: str, code_id: str) -> List[Dict[str, Any]]:
        """
        Extract raw articles from a government.ru HTML page (no validation).

        Collects raw articles without validating article numbers.
        Only processes content within <div class="reader_article_body"> elements.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            List of raw article dictionaries (with unvalidated article_number)
        """
        soup = BeautifulSoup(html, "html.parser")

        raw_articles = []
        current_article = None
        current_paragraphs = []

        # Track processed elements to avoid processing nested elements multiple times
        processed = set()
        # Track extracted article numbers to prevent duplicates from overlapping divs
        extracted_article_numbers = set()

        # CRITICAL: government.ru has content in <div class="reader_article_body">
        # We must ONLY process elements within these divs to avoid picking up UI noise
        article_body_divs = soup.find_all("div", class_="reader_article_body")

        if not article_body_divs:
            logger.warning(f"[{code_id}] No reader_article_body divs found in HTML")
            return []

        # Process elements within each reader_article_body div
        for article_body in article_body_divs:
            for element in article_body.find_all(["h3", "h4", "p", "div"]):
                # Skip if this element or any of its parents have been processed
                should_skip = False
                for parent in element.parents:
                    if parent in processed:
                        should_skip = True
                        break
                if should_skip:
                    continue

                # Get text - use .string for elements with only direct text
                if element.string and element.string.strip():
                    text = element.string.strip()
                else:
                    text = element.get_text(strip=True)

                article_match = re.match(
                    r"^Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)$", text, re.IGNORECASE
                )

                if article_match:
                    # Save previous article
                    if current_article and current_paragraphs:
                        current_article["article_text"] = "\n\n".join(current_paragraphs)
                        # Skip duplicate articles (can happen with overlapping divs)
                        if current_article["article_number"] not in extracted_article_numbers:
                            raw_articles.append(current_article)
                            extracted_article_numbers.add(current_article["article_number"])
                        else:
                            logger.debug(
                                f"[{code_id}] Skipping duplicate article {current_article['article_number']}"
                            )

                    # Start new article (keep raw number for now)
                    article_number = article_match.group(1)  # Preserve original format
                    article_title = text

                    current_article = {
                        "article_number": article_number,  # Raw number
                        "article_title": article_title,
                        "article_text": "",
                    }
                    current_paragraphs = []
                    # Reset paragraph counter for new article
                    self._expected_paragraph_num = 1
                    processed.add(element)

                elif current_article and text:
                    paragraph_match = re.match(r"^(\d+)\.\s*(.+)$", text)
                    if paragraph_match:
                        current_paragraphs.append(text)
                    else:
                        # Use helper function to filter UI noise
                        is_valid, filter_reason = self._is_valid_article_content(
                            text, "government", current_article.get("article_number")
                        )
                        if is_valid:
                            current_paragraphs.append(text)

        # Don't forget the last article
        if current_article and current_paragraphs:
            current_article["article_text"] = "\n\n".join(current_paragraphs)
            # Skip duplicate articles (can happen with overlapping divs)
            if current_article["article_number"] not in extracted_article_numbers:
                raw_articles.append(current_article)
            else:
                logger.debug(
                    f"[{code_id}] Skipping duplicate article {current_article['article_number']}"
                )

        return raw_articles

    def _validate_and_correct_articles(self, raw_articles: List[Dict], code_id: str) -> List[Dict[str, Any]]:
        """
        Validate and correct article numbers with full context.

        Takes a list of raw articles and validates/corrects their article numbers
        using context from previous and next articles. This enables proper
        correction of articles like "231" → "23.1" when prev_article is "23".

        Args:
            raw_articles: List of raw article dictionaries
            code_id: Code identifier

        Returns:
            List of validated/corrected article dictionaries
        """
        articles = []
        for i, raw_article in enumerate(raw_articles):
            raw_number = raw_article["article_number"]

            # Get context for validation
            # Use corrected previous article for context (not raw) - this allows proper sub-article detection
            prev_article = articles[i - 1]["article_number"] if i > 0 else None
            # Use raw next article for context (not yet corrected)
            next_article = raw_articles[i + 1]["article_number"] if i < len(raw_articles) - 1 else None

            # Log what we're parsing (verbose mode shows raw number and context)
            logger.debug(f"[{code_id}] Parsing article: '{raw_number}' (prev={prev_article}, next={next_article})")

            # Validate with hybrid approach
            corrected_number, warnings = validate_and_correct_article_number(
                raw_number, code_id, prev_article, next_article
            )

            # Log final result (verbose mode shows correction or validation)
            if corrected_number == raw_number:
                logger.debug(f"[{code_id}] Article '{raw_number}' validated - no change needed")
            else:
                logger.debug(f"[{code_id}] Article '{raw_number}' corrected to '{corrected_number}'")

            for warning in warnings:
                logger.warning(f"[{code_id}] {warning}")

            # Update title if article_number changed
            article_title = raw_article["article_title"]
            if corrected_number != raw_number:
                # Replace old article number in title with corrected one
                old_num_pattern = re.escape(raw_number)
                article_title = re.sub(
                    f"Статья\\s+{old_num_pattern}",
                    f"Статья {corrected_number}",
                    article_title,
                    flags=re.IGNORECASE
                )

            articles.append({
                **raw_article,
                "article_number": corrected_number,
                "article_title": article_title,
            })

        # Verbose mode: Summary of all article numbers (initial and saved)
        logger.debug(f"[{code_id}] Article numbers: initial → saved")
        for raw_article, final_article in zip(raw_articles, articles):
            raw_num = raw_article["article_number"]
            final_num = final_article["article_number"]
            if raw_num != final_num:
                logger.debug(f"[{code_id}]   '{raw_num}' → '{final_num}'")
            else:
                logger.debug(f"[{code_id}]   '{raw_num}' (no change)")

        return articles

    def _parse_single_government_page(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse a single government.ru HTML page to extract articles.

        Extracts raw articles and validates article numbers with context.
        Only processes content within <div class="reader_article_body"> elements.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        # Extract raw articles from the page
        raw_articles = self._extract_raw_articles_from_government_page(html, code_id)

        # Validate and correct article numbers with context
        validated_articles = self._validate_and_correct_articles(raw_articles, code_id)

        return {
            "code_id": code_id,
            "articles": validated_articles,
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

        # Step 2: Batch insert all articles in a single transaction
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
                        text_hash,
                        source
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
                        :text_hash,
                        :source
                    )
                    ON CONFLICT (code_id, article_number, version_date)
                    DO UPDATE SET
                        article_text = EXCLUDED.article_text,
                        article_title = EXCLUDED.article_title,
                        amendment_eo_number = EXCLUDED.amendment_eo_number,
                        is_current = EXCLUDED.is_current,
                        is_repealed = EXCLUDED.is_repealed,
                        text_hash = EXCLUDED.text_hash,
                        source = EXCLUDED.source
                """
                )

                # Prepare all parameters for batch insert
                params_list = []
                for article in articles:
                    params = {
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
                        "source": metadata.get("source", "unknown"),
                    }
                    params_list.append(params)

                # Single batch insert + commit
                conn.execute(insert_query, params_list)
                conn.commit()

                # Get actual unique article count (UPSERT may have overwritten duplicates)
                count_query = text(
                    """
                    SELECT COUNT(DISTINCT article_number) as unique_count
                    FROM code_article_versions
                    WHERE code_id = :code_id
                    """
                )
                result = conn.execute(count_query, {"code_id": code_id})
                saved = result.scalar()
                logger.debug(f"Saved {len(params_list)} articles (UPSERT operations), {saved} unique article numbers")

        except Exception as e:
            logger.error(f"Failed to save articles for {code_id}: {e}")
            return 0

        return saved

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Consultant.ru verification functions


def _is_valid_article_number(article_num: str) -> bool:
    """
    Validate if a scraped number is a valid article number.

    Filters out false positives like years (1875, 2026) or random numbers.

    Args:
        article_num: Article number to validate

    Returns:
        True if valid article number, False otherwise
    """
    # Must be non-empty
    if not article_num:
        return False

    # Check each part of the article number
    parts = article_num.split('.')
    for i, part in enumerate(parts):
        # Must be a valid number
        if not part.isdigit():
            return False

        num = int(part)

        # Filter out obvious false positives:
        # Note: Numeric filters (> 500, 1000-2999) removed because:
        # - GK_RF_4 articles start at 1225
        # - GK_RF_3 and GK_RF_2 have articles > 500
        # The link-based scraping with "Статья" prefix provides sufficient signal
        # Sub-article parts (parts after the first) shouldn't be > 100
        if i > 0 and num > 99:  # Only check sub-article parts, not main article number
            return False

    return True


def scrape_article_numbers_from_consultant(doc_id: str) -> List[str]:
    """
    Scrape all article numbers from a consultant.ru document page.

    Args:
        doc_id: Consultant.ru document ID (e.g., 'cons_doc_LAW_34661')

    Returns:
        List of article numbers found in the document
    """
    url = f"https://www.consultant.ru/document/{doc_id}/"
    article_numbers = []

    try:
        logger.info(f"Fetching article structure from {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all article links in the document
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text()

            # Skip chapter links (Глава) - we only want articles (Статья)
            if 'Глава' in link_text:
                continue

            # Match article pattern: e.g., "Статья 1.3.1" or just "1.3.1"
            # But only if it's actually an article link (contains "Статья")
            if 'Статья' in link_text:
                match = re.search(r'(?:Статья\s+)?(\d+(?:[\.\-]\d+)*)(?:\.|$)', link_text)
                if match:
                    article_num = match.group(1)
                    if article_num not in article_numbers and is_valid_article_number_format(article_num):
                        article_numbers.append(article_num)

        # Alternative: scrape from document text
        pattern = r'Статья\s+(\d+(?:[\.\-]\d+)*)(?:\.|\s|$)'
        for match in re.finditer(pattern, response.text):
            article_num = match.group(1)
            if article_num not in article_numbers and is_valid_article_number_format(article_num):
                article_numbers.append(article_num)

        # Sort using ArticleNumberParser for proper handling of hyphenated formats
        article_numbers.sort(key=lambda x: _article_parser.parse(x))
        logger.info(f"Found {len(article_numbers)} articles in consultant.ru structure")

    except Exception as e:
        logger.error(f"Failed to scrape article numbers from {url}: {e}")

    return article_numbers


def fetch_missing_article_titles(code_id: str, missing_articles: List[str]) -> Dict[str, str]:
    """
    Fetch article titles from consultant.ru for missing articles.

    Args:
        code_id: Code identifier (e.g., 'LK_RF')
        missing_articles: List of article numbers to fetch titles for

    Returns:
        Dictionary mapping article_number -> title
    """
    if code_id not in CONSULTANT_DOC_IDS:
        logger.warning(f"Code {code_id} not in CONSULTANT_DOC_IDS, cannot fetch titles")
        return {}

    doc_id = CONSULTANT_DOC_IDS[code_id]
    url = f"https://www.consultant.ru/document/{doc_id}/"
    titles: Dict[str, str] = {}

    try:
        logger.info(f"Fetching titles for {len(missing_articles)} missing articles from {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all article links and extract titles
        for link in soup.find_all('a', href=True):
            link_text = link.get_text()
            # Match "Статья X.Y" or "Статья X" pattern
            match = re.search(r'Статья\s+([\d.]+)\.?\s+(.+?)(?:\s*$|\s*\(ред)', link_text)
            if match:
                article_num = match.group(1)
                # Normalize article number (remove trailing dots)
                article_num = article_num.rstrip('.')
                if article_num in missing_articles:
                    title = match.group(2).strip()
                    # Clean up title (remove parenthetical notes, etc.)
                    title = re.sub(r'\s*\(.*?\)', '', title).strip()
                    titles[article_num] = title
                    logger.debug(f"Found title for article {article_num}: {title}")

        logger.info(f"Fetched {len(titles)} titles for missing articles")

    except Exception as e:
        logger.error(f"Failed to fetch article titles from {url}: {e}")

    return titles


def import_consultant_reference(code_id: str, article_numbers: List[str]) -> Dict[str, any]:
    """
    Import consultant.ru article number reference to database.

    Creates mappings from our format (official sources) to consultant.ru format.
    Also saves consultant articles that are missing from our database.

    Args:
        code_id: Code identifier
        article_numbers: List of article numbers from consultant.ru

    Returns:
        Dictionary with import results (matched_count, missing_count, missing_articles)
    """
    result = {
        "matched_count": 0,
        "missing_count": 0,
        "missing_articles": [],
    }

    try:
        with get_db_connection() as conn:
            # Ensure reference table exists with NULL support for missing articles
            create_table_query = text(
                """
                CREATE TABLE IF NOT EXISTS article_number_reference (
                    id SERIAL PRIMARY KEY,
                    code_id VARCHAR(50) NOT NULL,
                    article_number_source VARCHAR(50),  -- NULL for missing articles
                    article_number_consultant VARCHAR(50) NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    verification_notes TEXT,
                    created_at TIMESTAMP DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS idx_article_number_reference_code_id
                ON article_number_reference(code_id);

                CREATE INDEX IF NOT EXISTS idx_article_number_reference_consultant
                ON article_number_reference(code_id, article_number_consultant);

                -- Unique constraint for matched articles (article_number_source IS NOT NULL)
                CREATE UNIQUE INDEX IF NOT EXISTS idx_article_number_reference_matched_unique
                ON article_number_reference(code_id, article_number_source, article_number_consultant)
                WHERE article_number_source IS NOT NULL;

                -- Unique constraint for missing articles (article_number_source IS NULL)
                CREATE UNIQUE INDEX IF NOT EXISTS idx_article_number_reference_missing_unique
                ON article_number_reference(code_id, article_number_consultant)
                WHERE article_number_source IS NULL;
                """
            )
            conn.execute(create_table_query)

            # Get existing articles for matching
            our_articles_query = text(
                """
                SELECT article_number, article_title, text_hash
                FROM code_article_versions
                WHERE code_id = :code_id
                """
            )
            result_db = conn.execute(our_articles_query, {"code_id": code_id})
            our_articles = {row[0]: (row[1], row[2]) for row in result_db}
            logger.info(f"Found {len(our_articles)} existing articles for {code_id}")

            # Track matched and missing consultant articles
            matched_params = []
            missing_params = []
            matched_consultant_articles = set()

            for consultant_article in article_numbers:
                # Try to find matching article by similar number pattern
                possible_source_formats = []
                if consultant_article.count('.') >= 2:
                    # "1.3.1" -> look for "1.31"
                    parts = consultant_article.split('.')
                    if len(parts) == 3 and len(parts[1]) == 1:
                        possible_source_formats.append(f"{parts[0]}.{parts[1]}{parts[2]}")
                elif consultant_article.count('.') == 1:
                    # Direct match for dotted articles (e.g., "5.1", "12.3")
                    possible_source_formats.append(consultant_article)
                else:
                    # Simple numbered article (no dot) - direct match (e.g., "1", "2", "10")
                    possible_source_formats.append(consultant_article)

                # Find matching article in our database
                found = False
                for source_format in possible_source_formats:
                    if source_format in our_articles:
                        title, text_hash = our_articles[source_format]
                        matched_params.append({
                            "code_id": code_id,
                            "article_number_source": source_format,
                            "article_number_consultant": consultant_article,
                            "is_verified": True,
                            "verification_notes": f"Auto-matched: {source_format} -> {consultant_article}",
                        })
                        matched_consultant_articles.add(consultant_article)
                        logger.debug(f"Matched: {source_format} -> {consultant_article}")
                        found = True
                        break

                # If not found in our DB, add to missing list
                if not found and consultant_article not in matched_consultant_articles:
                    missing_params.append({
                        "code_id": code_id,
                        "article_number_source": None,  # NULL indicates missing
                        "article_number_consultant": consultant_article,
                        "is_verified": False,
                        "verification_notes": "",  # Will be filled after fetching titles
                    })
                    result["missing_articles"].append(consultant_article)
                    logger.debug(f"Missing article in our DB: {consultant_article}")

            # Fetch titles for missing articles from consultant.ru
            missing_articles_only = [p["article_number_consultant"] for p in missing_params]
            missing_titles = {}
            if missing_articles_only:
                missing_titles = fetch_missing_article_titles(code_id, missing_articles_only)
                result["missing_with_titles"] = missing_titles

            # Update missing params with titles and check for existing entries
            final_missing_params = []
            for params in missing_params:
                consultant_article = params["article_number_consultant"]

                # Check if this consultant article is already in reference table as missing
                existing_missing = conn.execute(
                    text("""
                        SELECT article_number_consultant FROM article_number_reference
                        WHERE code_id = :code_id
                        AND article_number_consultant = :consultant_article
                        AND article_number_source IS NULL
                    """),
                    {"code_id": code_id, "consultant_article": consultant_article}
                ).fetchone()

                if not existing_missing:
                    # Add title to verification_notes
                    title = missing_titles.get(consultant_article, "Unknown title")
                    params["verification_notes"] = f"Missing from official sources - Title: {title}"
                    final_missing_params.append(params)

            # Insert matched articles
            # Note: Using ON CONFLICT DO NOTHING because partial indexes don't work with ON CONFLICT
            # The unique index idx_article_number_reference_matched_unique has WHERE article_number_source IS NOT NULL
            if matched_params:
                insert_query = text(
                    """
                    INSERT INTO article_number_reference (
                        code_id, article_number_source, article_number_consultant,
                        is_verified, verification_notes
                    ) VALUES (
                        :code_id, :article_number_source, :article_number_consultant,
                        :is_verified, :verification_notes
                    )
                    ON CONFLICT DO NOTHING
                    """
                )
                conn.execute(insert_query, matched_params)
                result["matched_count"] = len(matched_params)

            # Insert missing articles (article_number_source is NULL)
            # Uses the article_number_reference_full_unique index (from migration 002)
            # which covers all three columns
            if final_missing_params:
                insert_missing_query = text(
                    """
                    INSERT INTO article_number_reference (
                        code_id, article_number_source, article_number_consultant,
                        is_verified, verification_notes
                    ) VALUES (
                        :code_id, :article_number_source, :article_number_consultant,
                        :is_verified, :verification_notes
                    )
                    ON CONFLICT (code_id, article_number_source, article_number_consultant)
                    DO NOTHING
                    """
                )
                conn.execute(insert_missing_query, final_missing_params)
                result["missing_count"] = len(final_missing_params)

            conn.commit()
            logger.info(
                f"Imported {result['matched_count']} matched mappings and "
                f"{result['missing_count']} missing articles for {code_id}"
            )

    except Exception as e:
        logger.error(f"Failed to import reference for {code_id}: {e}")

    return result


def verify_with_consultant(code_id: str) -> Dict[str, any]:
    """
    Verify imported articles against consultant.ru structure.

    Args:
        code_id: Code identifier to verify

    Returns:
        Dictionary with verification results
    """
    if code_id not in CONSULTANT_DOC_IDS:
        return {
            "code_id": code_id,
            "status": "skipped",
            "reason": "Not in consultant.ru mapping"
        }

    doc_id = CONSULTANT_DOC_IDS[code_id]
    logger.info(f"Verifying {code_id} against consultant.ru ({doc_id})")

    # Scrape consultant.ru structure
    consultant_articles = scrape_article_numbers_from_consultant(doc_id)

    if not consultant_articles:
        return {
            "code_id": code_id,
            "status": "error",
            "reason": "Failed to scrape consultant.ru"
        }

    # Import reference mappings (returns dict with matched_count, missing_count, missing_articles)
    import_result = import_consultant_reference(code_id, consultant_articles)

    # Get verification statistics
    try:
        with get_db_connection() as conn:
            # Get imported articles
            imp_query = text(
                """
                SELECT article_number
                FROM code_article_versions
                WHERE code_id = :code_id
                """
            )
            result = conn.execute(imp_query, {"code_id": code_id})
            imported_articles = set(row[0] for row in result)

            # Sample format differences
            format_diffs = []
            diff_query = text(
                """
                SELECT article_number_source, article_number_consultant
                FROM article_number_reference
                WHERE code_id = :code_id
                AND article_number_source IS NOT NULL
                AND article_number_source != article_number_consultant
                LIMIT 10
                """
            )
            result = conn.execute(diff_query, {"code_id": code_id})
            for row in result:
                format_diffs.append(f"{row[0]} -> {row[1]}")

            return {
                "code_id": code_id,
                "status": "success",
                "total_in_db": len(imported_articles),
                "total_in_consultant": len(consultant_articles),
                "matched_count": import_result.get("matched_count", 0),
                "missing_count": import_result.get("missing_count", 0),
                "missing_articles": import_result.get("missing_articles", []),
                "missing_with_titles": import_result.get("missing_with_titles", {}),
                "format_differences": format_diffs,
            }

    except Exception as e:
        logger.error(f"Failed to verify articles for {code_id}: {e}")
        return {
            "code_id": code_id,
            "status": "error",
            "reason": str(e)
        }


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
    parser.add_argument(
        "--verify-consultant",
        action="store_true",
        help="Verify imported articles against consultant.ru structure after import",
    )

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

                    # Run consultant verification for each part if requested
                    if args.verify_consultant:
                        print(f"\n{'─'*60}")
                        print("Verifying against consultant.ru...")
                        print(f"{'─'*60}")
                        for part_result in result.get("results", []):
                            part_code_id = part_result['code_id']
                            if part_code_id in CONSULTANT_DOC_IDS:
                                verify_result = verify_with_consultant(part_code_id)
                                print(f"\n{part_code_id}:")
                                print(f"  Status: {verify_result['status']}")
                                if verify_result['status'] == 'success':
                                    print(f"  In DB: {verify_result['total_in_db']}")
                                    print(f"  In consultant.ru: {verify_result['total_in_consultant']}")
                                    print(f"  Matched: {verify_result['matched_count']}")
                                    print(f"  Missing: {verify_result['missing_count']}")
                                    if verify_result['missing_articles']:
                                        print(f"  Missing articles (first 10):")
                                        missing_with_titles = verify_result.get('missing_with_titles', {})
                                        for art in verify_result['missing_articles'][:10]:
                                            title = missing_with_titles.get(art, "")
                                            if title:
                                                print(f"    - {art}: {title}")
                                            else:
                                                print(f"    - {art}")
                                    if verify_result['format_differences']:
                                        print(f"  Format differences (sample):")
                                        for diff in verify_result['format_differences'][:5]:
                                            print(f"    {diff}")
                                else:
                                    print(f"  Reason: {verify_result.get('reason', 'Unknown')}")
                            else:
                                print(f"\n{part_code_id}: Not in consultant.ru mapping")
                else:
                    # Single-part code
                    if result.get("pages_fetched"):
                        print(f"Pages Fetched: {result['pages_fetched']}")
                    print(f"Articles Found: {result['articles_found']}")
                    print(f"Articles Processed: {result.get('articles_processed', 0)}")
                    print(f"Articles Saved: {result['articles_saved']}")
                    print(f"Source: {result['source']}")

                    # Run consultant verification if requested
                    if args.verify_consultant:
                        print(f"\n{'─'*60}")
                        print("Verifying against consultant.ru...")
                        print(f"{'─'*60}")
                        verify_result = verify_with_consultant(args.code)
                        print(f"\nStatus: {verify_result['status']}")
                        if verify_result['status'] == 'success':
                            print(f"In DB: {verify_result['total_in_db']}")
                            print(f"In consultant.ru: {verify_result['total_in_consultant']}")
                            print(f"Matched: {verify_result['matched_count']}")
                            print(f"Missing: {verify_result['missing_count']}")
                            if verify_result['missing_articles']:
                                print(f"Missing articles (first 10):")
                                missing_with_titles = verify_result.get('missing_with_titles', {})
                                for art in verify_result['missing_articles'][:10]:
                                    title = missing_with_titles.get(art, "")
                                    if title:
                                        print(f"  - {art}: {title}")
                                    else:
                                        print(f"  - {art}")
                            if verify_result['format_differences']:
                                print(f"Format differences (sample):")
                                for diff in verify_result['format_differences'][:5]:
                                    print(f"  {diff}")
                        elif verify_result['status'] == 'skipped':
                            print(f"Skipped: {verify_result.get('reason', 'Unknown')}")
                        else:
                            print(f"Error: {verify_result.get('reason', 'Unknown')}")
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

            # Run consultant verification for all codes if requested
            if args.verify_consultant:
                print(f"\n{'='*60}")
                print("Consultant.ru Verification")
                print(f"{'='*60}")
                for code_id in CODE_METADATA.keys():
                    if code_id in CONSULTANT_DOC_IDS:
                        verify_result = verify_with_consultant(code_id)
                        status_symbol = "OK" if verify_result['status'] == 'success' else ("SKIP" if verify_result['status'] == 'skipped' else "ERR")
                        print(f"  [{status_symbol}] {code_id}: ", end="")
                        if verify_result['status'] == 'success':
                            print(f"DB={verify_result['total_in_db']}, consultant={verify_result['total_in_consultant']}, mappings={verify_result['matched_count']}")
                        else:
                            print(f"{verify_result.get('reason', 'Unknown')}")
                    else:
                        print(f"  [---] {code_id}: Not in consultant.ru mapping")

        else:
            parser.print_help()


if __name__ == "__main__":
    main()
