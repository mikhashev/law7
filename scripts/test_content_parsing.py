"""
Test script for content parsing from API metadata.

Tests the PravoContentParser with real data from the database.
Usage: poetry run python scripts/test_content_parsing.py --limit 5
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_db_connection
from parser.html_parser import PravoContentParser
from sqlalchemy import text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_content_parsing(limit: int = 5, skip_existing: bool = True):
    """
    Test content parsing from API metadata.

    Args:
        limit: Number of documents to test
        skip_existing: Skip documents that already have content
    """
    logger.info("="*60)
    logger.info("Testing Content Parsing from API Metadata")
    logger.info("="*60)

    parser = PravoContentParser()

    # Fetch documents from database
    skip_clause = "AND dc.full_text IS NULL" if skip_existing else ""
    query = f"""
        SELECT
            d.id,
            d.eo_number,
            d.title,
            d.name,
            d.complex_name,
            d.document_date,
            d.publish_date,
            d.pages_count,
            dc.full_text as existing_full_text,
            dc.text_hash as existing_text_hash
        FROM documents d
        LEFT JOIN document_content dc ON d.id = dc.document_id
        WHERE d.country_id = 1
        {skip_clause}
        ORDER BY d.publish_date DESC
        LIMIT {limit}
    """

    with get_db_connection() as conn:
        result = conn.execute(text(query))
        columns = result.keys()
        documents = [dict(zip(columns, row)) for row in result]

    if not documents:
        logger.warning("No documents found in database!")
        logger.info("  Run 'poetry run python scripts/sync/initial_sync.py --daily' to fetch documents")
        return

    logger.info(f"Found {len(documents)} documents to test\n")

    # Test parsing for each document
    success_count = 0
    fail_count = 0

    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        eo_number = doc["eo_number"]
        title = doc.get("complex_name", doc.get("title", "Unknown"))[:60]

        logger.info(f"[{i}/{len(documents)}] Testing: {title}...")
        logger.info(f"  eoNumber: {eo_number}")
        logger.info(f"  Existing content: {len(doc.get('existing_full_text') or '')} chars")

        # Prepare document data for parser
        doc_data = {
            "eoNumber": eo_number,
            "title": doc.get("title", ""),
            "name": doc.get("name", ""),
            "complexName": doc.get("complex_name", ""),
        }

        # Parse content
        try:
            parsed = parser.parse_document(doc_data)

            full_text = parsed.get("full_text", "")
            raw_text = parsed.get("raw_text", "")
            pdf_url = parsed.get("pdf_url", "")
            html_url = parsed.get("html_url", "")
            text_hash = parsed.get("text_hash", "")

            logger.info(f"  Parsed full_text: {len(full_text)} chars")
            logger.info(f"  PDF URL: {pdf_url}")
            logger.info(f"  HTML URL: {html_url}")
            logger.info(f"  Text hash: {text_hash[:16]}...")

            # Show preview of parsed text
            if full_text:
                preview = full_text[:200].replace("\n", " ")
                logger.info(f"  Preview: {preview}...")
                success_count += 1
            else:
                logger.warning(f"  No content extracted!")
                fail_count += 1

        except Exception as e:
            logger.error(f"  Failed: {e}")
            fail_count += 1

        logger.info("")

    # Summary
    logger.info("="*60)
    logger.info("Test Summary")
    logger.info("="*60)
    logger.info(f"Total tested: {len(documents)}")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info("="*60)

    # If all successful, suggest running full sync
    if fail_count == 0 and success_count > 0:
        logger.info("\nTo parse and store content for all documents:")
        logger.info("  poetry run python scripts/sync/content_sync.py --skip-embeddings")


def test_live_api_fetch(limit: int = 1):
    """
    Test fetching and parsing directly from pravo.gov.ru API.

    This bypasses the database to test the API directly.
    """
    logger.info("="*60)
    logger.info("Testing Live API Fetch from pravo.gov.ru")
    logger.info("="*60)

    from crawler.pravo_api_client import PravoApiClient

    client = PravoApiClient()

    # Fetch recent documents (use a past date range that has data)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = "2025-01-01"  # Use a date range that likely has data

    logger.info(f"Fetching documents from {start_date} to {end_date}...")

    result = client.search_documents(
        page=1,
        page_size=limit,
        start_date=yesterday,
        end_date=today,
    )

    items = result.get("items", [])
    logger.info(f"Found {len(items)} documents\n")

    parser = PravoContentParser()

    for i, item in enumerate(items, 1):
        logger.info(f"[{i}/{len(items)}] {item.get('complexName', item.get('name', 'Unknown'))[:60]}")

        parsed = parser.parse_document(item)

        logger.info(f"  eoNumber: {parsed['eo_number']}")
        logger.info(f"  Parsed text: {len(parsed['full_text'])} chars")
        logger.info(f"  PDF URL: {parsed['pdf_url']}")
        logger.info("")

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Test content parsing")
    parser.add_argument("--limit", type=int, default=5, help="Number of documents to test")
    parser.add_argument("--include-existing", action="store_true", help="Include documents with existing content")
    parser.add_argument("--live-api", action="store_true", help="Test live API fetch instead of database")

    args = parser.parse_args()

    if args.live_api:
        test_live_api_fetch(limit=args.limit)
    else:
        test_content_parsing(limit=args.limit, skip_existing=not args.include_existing)


if __name__ == "__main__":
    main()
