"""
Fetch Full Amendment Content from pravo.gov.ru

This script fetches detailed amendment text from pravo.gov.ru HTML pages
and updates the document_content table with full text content.

Usage:
    python -m scripts.sync.fetch_amendment_content --code TK_RF
    python -m scripts.sync.fetch_amendment_content --all
    python -m scripts.sync.fetch_amendment_content --eo-number 0001202512290020
"""
import argparse
import logging
import sys
import time
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text

from scripts.core.config import AMENDMENT_BATCH_SIZE, AMENDMENT_IMPORT_REQUEST_DELAY
from scripts.core.db import get_db_connection
# Updated import to use new country_modules location
from country_modules.russia.parsers.html_scraper import scrape_amendment

logger = logging.getLogger(__name__)


# Code names for filtering
CODE_NAMES = {
    'TK_RF': 'Трудовой кодекс',
    'GK_RF': 'Гражданский кодекс',
    'UK_RF': 'Уголовный кодекс',
    'NK_RF': 'Налоговый кодекс',
    'KoAP_RF': 'Кодекс об административных правонарушениях',
    'SK_RF': 'Семейный кодекс',
    'ZhK_RF': 'Жилищный кодекс',
    'ZK_RF': 'Земельный кодекс',
}


def get_amendments_for_code(code_id: str) -> List[tuple]:
    """
    Get list of amendments for a specific code.

    Args:
        code_id: Code identifier (e.g., 'TK_RF')

    Returns:
        List of (document_id, eo_number) tuples
    """
    code_name = CODE_NAMES.get(code_id)
    if not code_name:
        logger.error(f"Unknown code_id: {code_id}")
        return []

    query = """
        SELECT
            d.id,
            d.eo_number,
            d.name
        FROM documents d
        LEFT JOIN document_content dc ON d.id = dc.document_id
        WHERE d.name LIKE :code_pattern
        AND (
            dc.full_text IS NULL
            OR LENGTH(dc.full_text) < 500
        )
        ORDER BY d.document_date DESC
    """

    try:
        with get_db_connection() as conn:
            result = conn.execute(
                text(query),
                {'code_pattern': f'%{code_name}%'}
            )
            return [(row[0], row[1], row[2]) for row in result]
    except Exception as e:
        logger.error(f"Failed to fetch amendments: {e}")
        return []


def get_all_amendments() -> List[tuple]:
    """
    Get all amendments that need full text fetched.

    Returns:
        List of (document_id, eo_number, name) tuples
    """
    query = """
        SELECT
            d.id,
            d.eo_number,
            d.name
        FROM documents d
        LEFT JOIN document_content dc ON d.id = dc.document_id
        WHERE dc.full_text IS NULL
        OR LENGTH(dc.full_text) < 500
        ORDER BY d.document_date DESC
        LIMIT 100
    """

    try:
        with get_db_connection() as conn:
            result = conn.execute(text(query))
            return [(row[0], row[1], row[2]) for row in result]
    except Exception as e:
        logger.error(f"Failed to fetch amendments: {e}")
        return []


def update_amendment_content(document_id: str, full_text: str, effective_date: Optional[str] = None) -> bool:
    """
    Update document content with fetched full text.

    Args:
        document_id: Document UUID
        full_text: Full amendment text
        effective_date: Optional effective date

    Returns:
        True if update successful
    """
    try:
        with get_db_connection() as conn:
            # Check if content exists
            check_query = text("""
                SELECT id FROM document_content WHERE document_id = :doc_id
            """)
            existing = conn.execute(check_query, {'doc_id': document_id}).fetchone()

            if existing:
                # Update existing content
                update_query = text("""
                    UPDATE document_content
                    SET full_text = :full_text,
                        updated_at = NOW()
                    WHERE document_id = :doc_id
                """)
                conn.execute(update_query, {
                    'doc_id': document_id,
                    'full_text': full_text
                })
            else:
                # Insert new content
                insert_query = text("""
                    INSERT INTO document_content (id, document_id, full_text, created_at, updated_at)
                    VALUES (gen_random_uuid(), :doc_id, :full_text, NOW(), NOW())
                """)
                conn.execute(insert_query, {
                    'doc_id': document_id,
                    'full_text': full_text
                })

            conn.commit()
            logger.debug(f"Updated content for document {document_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to update content for {document_id}: {e}")
        return False


def batch_update_amendment_content(updates: List[dict]) -> int:
    """
    Update multiple amendments in a single database transaction.

    Args:
        updates: List of dicts with document_id, full_text, and optional effective_date

    Returns:
        Number of successfully updated amendments
    """
    if not updates:
        return 0

    try:
        with get_db_connection() as conn:
            successful = 0
            for update in updates:
                document_id = update['document_id']
                full_text = update['full_text']
                effective_date = update.get('effective_date')

                # Check if content exists
                check_query = text("""
                    SELECT id FROM document_content WHERE document_id = :doc_id
                """)
                existing = conn.execute(check_query, {'doc_id': document_id}).fetchone()

                if existing:
                    # Update existing content
                    update_query = text("""
                        UPDATE document_content
                        SET full_text = :full_text,
                            updated_at = NOW()
                        WHERE document_id = :doc_id
                    """)
                    conn.execute(update_query, {
                        'doc_id': document_id,
                        'full_text': full_text
                    })
                else:
                    # Insert new content
                    insert_query = text("""
                        INSERT INTO document_content (id, document_id, full_text, created_at, updated_at)
                        VALUES (gen_random_uuid(), :doc_id, :full_text, NOW(), NOW())
                    """)
                    conn.execute(insert_query, {
                        'doc_id': document_id,
                        'full_text': full_text
                    })

                successful += 1

            # Single commit for all updates
            conn.commit()
            logger.debug(f"Batch updated {successful} amendments")
            return successful

    except Exception as e:
        logger.error(f"Failed to batch update amendments: {e}")
        return 0


def fetch_amendment(eo_number: str, document_id: str, name: str) -> dict:
    """
    Fetch full content for a single amendment.

    Args:
        eo_number: Amendment document number
        document_id: Document UUID in database
        name: Document name

    Returns:
        Result dictionary with status and info
    """
    logger.info(f"Fetching {eo_number}: {name}")

    try:
        # Use HTML scraper to fetch full content
        result = scrape_amendment(eo_number)

        if not result.get('full_text'):
            return {
                'eo_number': eo_number,
                'status': 'failed',
                'error': 'No content returned'
            }

        # Update database with full text
        success = update_amendment_content(
            document_id=document_id,
            full_text=result['full_text'],
            effective_date=result.get('effective_date')
        )

        if success:
            return {
                'eo_number': eo_number,
                'status': 'success',
                'text_length': len(result['full_text']),
                'articles_found': len(result.get('articles_affected', [])),
                'changes_found': len(result.get('changes', [])),
            }
        else:
            return {
                'eo_number': eo_number,
                'status': 'failed',
                'error': 'Database update failed'
            }

    except Exception as e:
        logger.error(f"Error fetching {eo_number}: {e}")
        return {
            'eo_number': eo_number,
            'status': 'error',
            'error': str(e)
        }


def fetch_batch(amendments: List[tuple]) -> dict:
    """
    Fetch full content for a batch of amendments.

    Fetches content one by one (with rate limiting delays) but saves to database
    in batches for better performance.

    Args:
        amendments: List of (document_id, eo_number, name) tuples

    Returns:
        Summary dictionary with results
    """
    results = {
        'total': len(amendments),
        'success': 0,
        'failed': 0,
        'error': 0,
        'total_chars': 0,
        'details': []
    }

    logger.info(f"Fetching {len(amendments)} amendments...")
    logger.info(f"Rate limit delay: {AMENDMENT_IMPORT_REQUEST_DELAY} seconds between requests")
    logger.info(f"DB batch size: {AMENDMENT_BATCH_SIZE}")

    # Collect updates for batched database operations
    pending_updates = []

    for i, (document_id, eo_number, name) in enumerate(amendments):
        logger.info(f"Fetching {eo_number}: {name}")

        try:
            # Fetch content (without DB save)
            scrape_result = scrape_amendment(eo_number)

            if not scrape_result.get('full_text'):
                result = {
                    'eo_number': eo_number,
                    'status': 'failed',
                    'error': 'No content returned'
                }
            else:
                # Collect for batch update
                pending_updates.append({
                    'document_id': document_id,
                    'full_text': scrape_result['full_text'],
                    'effective_date': scrape_result.get('effective_date')
                })

                result = {
                    'eo_number': eo_number,
                    'status': 'pending_batch',
                    'text_length': len(scrape_result['full_text']),
                    'articles_found': len(scrape_result.get('articles_affected', [])),
                    'changes_found': len(scrape_result.get('changes', [])),
                }

        except Exception as e:
            logger.error(f"Error fetching {eo_number}: {e}")
            result = {
                'eo_number': eo_number,
                'status': 'error',
                'error': str(e)
            }

        results['details'].append(result)

        # Add delay between requests (except after last one)
        if i < len(amendments) - 1:
            logger.debug(f"Waiting {AMENDMENT_IMPORT_REQUEST_DELAY}s before next request...")
            time.sleep(AMENDMENT_IMPORT_REQUEST_DELAY)

        # Flush batch when size reached or at end
        if len(pending_updates) >= AMENDMENT_BATCH_SIZE or i == len(amendments) - 1:
            if pending_updates:
                logger.info(f"Saving batch of {len(pending_updates)} amendments to database...")
                saved_count = batch_update_amendment_content(pending_updates)

                # Update results based on actual saves
                for detail in results['details']:
                    if detail['status'] == 'pending_batch':
                        detail['status'] = 'success' if saved_count > 0 else 'failed'
                        if detail['status'] == 'success':
                            results['success'] += 1
                            results['total_chars'] += detail.get('text_length', 0)
                        else:
                            results['failed'] += 1

                pending_updates = []

    # Count final failures and errors
    for detail in results['details']:
        if detail['status'] == 'failed':
            results['failed'] += 1
        elif detail['status'] == 'error':
            results['error'] += 1

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch full amendment content from pravo.gov.ru"
    )
    parser.add_argument(
        '--code',
        choices=list(CODE_NAMES.keys()),
        help='Fetch amendments for specific code'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Fetch all amendments that need content'
    )
    parser.add_argument(
        '--eo-number',
        help='Fetch specific amendment by EO number'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Limit number of amendments to process (default: 50)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # Set UTF-8 for Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    # Get amendments to process
    amendments = []

    if args.eo_number:
        # Fetch specific amendment
        query = text("""
            SELECT id, eo_number, name FROM documents WHERE eo_number = :eo_number
        """)
        with get_db_connection() as conn:
            result = conn.execute(query, {'eo_number': args.eo_number})
            row = result.fetchone()
            if row:
                amendments = [(row[0], row[1], row[2])]
            else:
                logger.error(f"Amendment not found: {args.eo_number}")
                sys.exit(1)

    elif args.code:
        # Fetch amendments for specific code
        amendments = get_amendments_for_code(args.code)
        amendments = amendments[:args.limit]

    elif args.all:
        # Fetch all amendments that need content
        amendments = get_all_amendments()

    else:
        parser.print_help()
        sys.exit(1)

    if not amendments:
        logger.info("No amendments to process")
        sys.exit(0)

    # Fetch content
    start_time = datetime.now()
    results = fetch_batch(amendments)
    elapsed = (datetime.now() - start_time).total_seconds()

    # Print summary
    print("\n" + "="*60)
    print("Fetch Summary")
    print("="*60)
    print(f"Total processed: {results['total']}")
    print(f"Successful: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Errors: {results['error']}")
    print(f"Total characters: {results['total_chars']:,}")
    print(f"Time elapsed: {elapsed:.1f}s")
    print("="*60)

    if results['failed'] > 0:
        print("\nFailed amendments:")
        for detail in results['details']:
            if detail['status'] == 'failed':
                print(f"  - {detail['eo_number']}: {detail.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
