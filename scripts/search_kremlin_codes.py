"""
Search Kremlin.ru for Legal Code Bank IDs

This script searches the official publication portal (kremlin.ru)
to find the bank IDs for all Russian legal codes.

Usage:
    python scripts/search_kremlin_codes.py
"""
import logging
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Codes to search for
CODES_TO_SEARCH = {
    'TK_RF': 'Трудовой кодекс',
    'GK_RF': 'Гражданский кодекс',
    'UK_RF': 'Уголовный кодекс',
    'NK_RF': 'Налоговый кодекс',
    'KoAP_RF': 'Кодекс об административных правонарушениях',
    'SK_RF': 'Семейный кодекс',
    'ZhK_RF': 'Жилищный кодекс',
    'ZK_RF': 'Земельный кодекс',
}


def search_kremlin(code_name: str, timeout: int = 30) -> Optional[str]:
    """
    Search kremlin.ru for a specific code.

    Args:
        code_name: Name of the code to search for
        timeout: Request timeout in seconds

    Returns:
        Bank ID if found, None otherwise
    """
    search_url = f"http://www.kremlin.ru/acts/bank/search?title={quote(code_name)}&type=1"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        logger.info(f"Searching for: {code_name}")
        response = requests.get(search_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # Look for result links
        # Pattern: /acts/bank/XXXXX
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Match bank link pattern
            bank_match = re.search(r'/acts/bank/(\d+)', href)
            if bank_match and code_name.lower() in text.lower():
                bank_id = bank_match.group(1)
                logger.info(f"  Found: {text} -> {href}")
                return bank_id

        logger.warning(f"  No results found for: {code_name}")
        return None

    except Exception as e:
        logger.error(f"  Error searching for {code_name}: {e}")
        return None


def search_all_codes() -> Dict[str, Optional[str]]:
    """
    Search for all codes and return bank IDs.

    Returns:
        Dictionary mapping code_id to bank_id
    """
    results = {}

    print("Searching Kremlin.ru for legal code bank IDs...\n")

    for code_id, code_name in CODES_TO_SEARCH.items():
        bank_id = search_kremlin(code_name)
        results[code_id] = bank_id

        # Small delay between requests
        import time
        time.sleep(0.5)

    print("\n" + "="*60)
    print("Search Results")
    print("="*60)

    for code_id, bank_id in results.items():
        status = f"[OK] {bank_id}" if bank_id else "[NOT FOUND]"
        print(f"  {code_id}: {CODES_TO_SEARCH[code_id]} {status}")

    print("="*60)

    found_count = sum(1 for v in results.values() if v)
    print(f"Found: {found_count}/{len(results)} codes")

    return results


def print_pyth_on_results(results: Dict[str, Optional[str]]):
    """Print results in Python dict format for easy copy-paste."""
    print("\n" + "="*60)
    print("Python Format for CODE_METADATA")
    print("="*60)

    for code_id, bank_id in results.items():
        if bank_id:
            print(f"    '{code_id}': {{")
            print(f"        'kremlin_bank': '{bank_id}',")
            print(f"        'kremlin_url': f\"http://www.kremlin.ru/acts/bank/{bank_id}\",")
            print(f"    }},")
        else:
            print(f"    '{code_id}': {{")
            print(f"        'kremlin_bank': None,  # TODO: Search manually")
            print(f"        'kremlin_url': None,")
            print(f"    }},")

    print("="*60)


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # Set UTF-8 for Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    results = search_all_codes()
    print_pyth_on_results(results)


if __name__ == "__main__":
    main()
