"""
On-Demand Document Search and Ingestion

Searches kremlin.ru for legal documents and ingests them into law7 database.
Called by MCP server when query-laws returns no results.

Usage:
    python scripts/search_and_ingest.py --query "Центральный банк" --type 5 --max 10

Document types (type parameter):
    "" = All
    "1" = Code (Кодекс)
    "3" = Decree (Указ)
    "4" = Order (Распоряжение)
    "5" = Federal Law (Федеральный закон)
    "6" = Constitutional Federal Law (Федеральный конституционный закон)
    "7" = Message (Послание)
    "8" = Constitutional Amendment (Закон о поправке к Конституции)
"""
import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

# Add parent directory to path for imports (cross-platform)
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from scripts.core.db import get_db_connection, execute_sql, execute_sql_write
from scripts.core.config import config

logger = logging.getLogger(__name__)

# Constants
KREMLIN_BASE_URL = "http://www.kremlin.ru"
KREMLIN_SEARCH_URL = f"{KREMLIN_BASE_URL}/acts/bank/search"
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.0  # Delay between requests to be polite

# Document type mapping from kremlin.ru type codes to law7 document_types
KREMLIN_TYPE_TO_DB_TYPE = {
    "1": "36fd214d-52fb-44b8-b22d-6f9e2f5004d8",  # Кодекс
    "3": "0790e34b-784b-4372-884e-3282622a24bd",  # Указ
    "4": "7ff5b3b5-3757-44f1-bb76-3766cabe3593",  # Распоряжение
    "5": "82a8bf1c-3bc7-47ed-827f-7affd43a7f27",  # Федеральный закон
    "6": "93273da3-3133-4acf-96c2-4adc1ae70e19",  # Федеральный конституционный закон
    "7": None,  # Послание (not in DB types, will be null)
    "8": "e0c56da5-17f1-40ac-a10f-8a9a1cee0c4e",  # Закон о поправке к Конституции
}

# Russia country ID
RUSSIA_COUNTRY_ID = 1

# President publication block ID
PRESIDENT_BLOCK_ID = "e94b6872-dcac-414f-b2f1-a538d13a12a0"


def search_kremlin(
    query: str,
    doc_type: str = "",
    page: int = 1,
    search_mode: str = "text",
    timeout: int = REQUEST_TIMEOUT
) -> List[Dict[str, Any]]:
    """
    Search kremlin.ru for documents.

    Args:
        query: Search query in Russian
        doc_type: Document type filter (kremlin type code)
        page: Page number (1-indexed)
        search_mode: "text" for full-text search, "title" for title-only search
        timeout: Request timeout in seconds

    Returns:
        List of document dictionaries with bank_id, title, url, etc.
    """
    # Kremlin supports two search modes:
    # - ?query=... (full-text search in document content)
    # - ?title=... (search by document title/number only)
    params = {
        "page": page,
    }
    if search_mode == "title":
        params["title"] = query
    else:
        params["query"] = query
    if doc_type:
        params["type"] = doc_type

    headers = {
        "User-Agent": "Law7-OnDemand-Scraper/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        logger.info(f"Searching kremlin.ru: query='{query}', type='{doc_type}', page={page}")
        response = requests.get(
            KREMLIN_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        # Find all result links with bank pattern
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Match /acts/bank/XXXXX pattern
            bank_match = re.search(r'/acts/bank/(\d+)', href)
            if bank_match and text:
                bank_id = bank_match.group(1)
                results.append({
                    'bank_id': bank_id,
                    'title': text,
                    'url': f"{KREMLIN_BASE_URL}/acts/bank/{bank_id}",
                })

        logger.info(f"Found {len(results)} results on page {page}")
        return results

    except requests.RequestException as e:
        logger.error(f"Error searching kremlin.ru: {e}")
        return []


def fetch_document_full_text(
    bank_id: str,
    timeout: int = REQUEST_TIMEOUT
) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch full text of a document from kremlin.ru.

    Kremlin documents are paginated, so we need to fetch all pages.

    Args:
        bank_id: Kremlin bank ID
        timeout: Request timeout in seconds

    Returns:
        Tuple of (full text, pravo_nd) where pravo_nd is the nd parameter
        from pravo.gov.ru link, or None if not found
    """
    pravo_nd = None
    headers = {
        "User-Agent": "Law7-OnDemand-Scraper/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    full_text_parts = []
    page = 1
    max_pages = 100  # Safety limit

    try:
        while page <= max_pages:
            url = f"{KREMLIN_BASE_URL}/acts/bank/{bank_id}/pages/{page}"
            logger.info(f"Fetching page {page}: {url}")

            response = requests.get(url, headers=headers, timeout=timeout)

            # 404 means no more pages
            if response.status_code == 404:
                if page == 1:
                    # Try without /pages/1 for single-page documents
                    url = f"{KREMLIN_BASE_URL}/acts/bank/{bank_id}"
                    response = requests.get(url, headers=headers, timeout=timeout)
                    if response.status_code == 404:
                        logger.warning(f"Document not found: {bank_id}")
                        return None, None
                else:
                    # No more pages
                    break

            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract pravo.gov.ru nd parameter from link (only on first page)
            if page == 1 and pravo_nd is None:
                pravo_link = soup.find('a', href=re.compile(r'pravo\.gov\.ru/proxy/ips.*nd=\d+'))
                if pravo_link:
                    href = pravo_link.get('href', '')
                    nd_match = re.search(r'nd=(\d+)', href)
                    if nd_match:
                        pravo_nd = nd_match.group(1)
                        logger.info(f"Found pravo.gov.ru nd={pravo_nd}")

            # Find the main content area
            # Kremlin uses various content containers
            content_selectors = [
                'div.reading__content',
                'div.entry__content',
                'div.document__content',
                'article',
                'div.content',
            ]

            page_text = None
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    # Remove script and style tags
                    for tag in content.find_all(['script', 'style', 'nav', 'footer']):
                        tag.decompose()
                    page_text = content.get_text(separator='\n', strip=True)
                    break

            if not page_text:
                # Fallback: get all paragraph text
                paragraphs = soup.find_all('p')
                page_text = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

            if page_text:
                full_text_parts.append(page_text)

            # Check if there's a next page link
            next_link = soup.find('a', href=re.compile(rf'/acts/bank/{bank_id}/pages/{page + 1}'))
            if not next_link:
                # Check for pagination indicator
                has_more = soup.find('a', class_='pager__item_next')
                if not has_more:
                    break

            page += 1
            time.sleep(REQUEST_DELAY)  # Be polite

        if full_text_parts:
            full_text = '\n\n'.join(full_text_parts)
            logger.info(f"Fetched {len(full_text)} characters from {page} page(s)")
            return full_text, pravo_nd
        else:
            logger.warning(f"No content found for document {bank_id}")
            return None, None

    except requests.RequestException as e:
        logger.error(f"Error fetching document {bank_id}: {e}")
        return None


def get_document_type_id(kremlin_type: str) -> Optional[str]:
    """Convert kremlin type code to law7 document_type_id."""
    return KREMLIN_TYPE_TO_DB_TYPE.get(kremlin_type)


def check_document_exists(eo_number: str) -> bool:
    """Check if a document already exists in the database."""
    with get_db_connection() as conn:
        result = conn.execute(
            text("SELECT 1 FROM documents WHERE eo_number = :eo_number"),
            {"eo_number": eo_number}
        )
        return result.fetchone() is not None


def extract_eo_number_from_bank_id(bank_id: str, pravo_nd: Optional[str] = None) -> str:
    """
    Generate eo_number from bank_id or pravo_nd.

    Args:
        bank_id: Kremlin bank ID
        pravo_nd: pravo.gov.ru nd parameter (if found)

    Returns:
        eo_number - uses pravo_nd if available, otherwise KREMLIN_{bank_id}
    """
    if pravo_nd:
        return pravo_nd  # Use pravo.gov.ru nd as eo_number
    return f"KREMLIN_{bank_id}"


def ingest_document(
    bank_id: str,
    title: str,
    full_text: Optional[str],
    doc_type: str = "",
    persist: bool = True,
    pravo_nd: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ingest a document into the law7 database.

    Args:
        bank_id: Kremlin bank ID
        title: Document title
        full_text: Full text content
        doc_type: Kremlin document type code
        persist: Whether to save to database
        pravo_nd: pravo.gov.ru nd parameter (if found)

    Returns:
        Dictionary with ingestion result
    """
    eo_number = extract_eo_number_from_bank_id(bank_id, pravo_nd)

    result = {
        'bank_id': bank_id,
        'eo_number': eo_number,
        'pravo_nd': pravo_nd,
        'title': title,
        'url': f"{KREMLIN_BASE_URL}/acts/bank/{bank_id}",
        'ingested': False,
        'skipped': False,
        'error': None,
    }

    if not persist:
        result['skipped'] = True
        result['reason'] = 'persist=False'
        return result

    # Check if document already exists
    if check_document_exists(eo_number):
        result['skipped'] = True
        result['reason'] = 'already_exists'
        logger.info(f"Document {eo_number} already exists, skipping")
        return result

    try:
        document_type_id = get_document_type_id(doc_type)

        # Insert into documents table
        with get_db_connection() as conn:
            # Insert document metadata
            insert_result = conn.execute(
                text("""
                    INSERT INTO documents
                    (eo_number, title, country_id, document_type_id, publication_block_id)
                    VALUES
                    (:eo_number, :title, :country_id, :document_type_id, :publication_block_id)
                    RETURNING id
                """),
                {
                    "eo_number": eo_number,
                    "title": title,
                    "country_id": RUSSIA_COUNTRY_ID,
                    "document_type_id": document_type_id,
                    "publication_block_id": PRESIDENT_BLOCK_ID,
                }
            )

            doc_row = insert_result.fetchone()
            if not doc_row:
                raise Exception("Failed to get document ID after insert")

            document_id = doc_row[0]

            # Insert document content
            text_hash = hashlib.sha256((full_text or "").encode('utf-8')).hexdigest() if full_text else None

            conn.execute(
                text("""
                    INSERT INTO document_content
                    (document_id, full_text, html_url, text_hash)
                    VALUES
                    (:document_id, :full_text, :html_url, :text_hash)
                """),
                {
                    "document_id": document_id,
                    "full_text": full_text,
                    "html_url": f"{KREMLIN_BASE_URL}/acts/bank/{bank_id}",
                    "text_hash": text_hash,
                }
            )

            conn.commit()

        result['ingested'] = True
        result['document_id'] = str(document_id)
        logger.info(f"Successfully ingested document {eo_number}")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error ingesting document {eo_number}: {e}")

    return result


def search_and_ingest(
    query: str,
    doc_type: str = "",
    max_results: int = 10,
    persist: bool = True,
    fetch_content: bool = True,
    search_mode: str = "text"
) -> Dict[str, Any]:
    """
    Search kremlin.ru and ingest results into law7 database.

    Args:
        query: Search query in Russian
        doc_type: Kremlin document type filter
        max_results: Maximum number of results to process
        persist: Whether to save to database
        fetch_content: Whether to fetch full text content
        search_mode: "text" for full-text search, "title" for title-only search

    Returns:
        Dictionary with search results and ingestion status
    """
    logger.info(f"Starting search and ingest: query='{query}', type='{doc_type}', mode='{search_mode}', max={max_results}")

    results = {
        'query': query,
        'doc_type': doc_type,
        'search_mode': search_mode,
        'timestamp': datetime.now().isoformat(),
        'total_found': 0,
        'processed': 0,
        'ingested': 0,
        'skipped': 0,
        'errors': 0,
        'documents': [],
    }

    # Search kremlin.ru
    search_results = search_kremlin(query, doc_type, search_mode=search_mode)
    results['total_found'] = len(search_results)

    # Process results
    for i, doc in enumerate(search_results[:max_results]):
        logger.info(f"Processing {i+1}/{min(len(search_results), max_results)}: {doc['bank_id']}")

        # Fetch full text if requested
        full_text = None
        pravo_nd = None
        if fetch_content:
            full_text, pravo_nd = fetch_document_full_text(doc['bank_id'])
            time.sleep(REQUEST_DELAY)  # Be polite

        # Ingest document
        ingest_result = ingest_document(
            bank_id=doc['bank_id'],
            title=doc['title'],
            full_text=full_text,
            doc_type=doc_type,
            persist=persist,
            pravo_nd=pravo_nd
        )

        results['documents'].append(ingest_result)
        results['processed'] += 1

        if ingest_result.get('ingested'):
            results['ingested'] += 1
        elif ingest_result.get('skipped'):
            results['skipped'] += 1
        else:
            results['errors'] += 1

    logger.info(f"Search and ingest complete: processed={results['processed']}, ingested={results['ingested']}, skipped={results['skipped']}, errors={results['errors']}")

    return results


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Search kremlin.ru and ingest documents into law7 database"
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Search query in Russian"
    )
    parser.add_argument(
        "--type", "-t",
        default="",
        choices=["", "1", "3", "4", "5", "6", "7", "8"],
        help="Document type filter (kremlin type code)"
    )
    parser.add_argument(
        "--mode", "-M",
        default="text",
        choices=["text", "title"],
        help="Search mode: 'text' for full-text search, 'title' for title-only search (default: text)"
    )
    parser.add_argument(
        "--max", "-m",
        type=int,
        default=10,
        help="Maximum number of results to process (default: 10)"
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Don't save to database (dry run)"
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="Don't fetch full text content (faster)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run search and ingest
    results = search_and_ingest(
        query=args.query,
        doc_type=args.type,
        max_results=args.max,
        persist=not args.no_persist,
        fetch_content=not args.no_content,
        search_mode=args.mode
    )

    # Output results
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Search and Ingest Results")
        print(f"{'='*60}")
        print(f"Query: {results['query']}")
        print(f"Type: {results['doc_type'] or 'All'}")
        print(f"Total found: {results['total_found']}")
        print(f"Processed: {results['processed']}")
        print(f"Ingested: {results['ingested']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Errors: {results['errors']}")
        print(f"{'='*60}")

        for doc in results['documents']:
            status = "[OK]" if doc.get('ingested') else "[SKIP]" if doc.get('skipped') else "[ERR]"
            print(f"{status} {doc['eo_number']}: {doc['title'][:60]}...")
            if doc.get('error'):
                print(f"    Error: {doc['error']}")


if __name__ == "__main__":
    main()
