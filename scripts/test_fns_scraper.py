#!/usr/bin/env python3
"""
Test FNS scraper implementation.

This script tests the FNS scraper for nalog.gov.ru to verify
the implementation works before running the full import.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.country_modules.russia.scrapers.ministry_scraper import MinistryScraper
from scripts.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_fns_manifest():
    """Test FNS manifest fetching."""
    logger.info("Testing FNS manifest fetching...")

    scraper = MinistryScraper("fns")
    manifest = await scraper.fetch_manifest()

    logger.info(f"FNS Manifest results:")
    logger.info(f"  Agency: {manifest['agency_name_short']}")
    logger.info(f"  Letters found: {len(manifest['letters'])}")
    logger.info(f"  Total available: {manifest['metadata'].get('total_found', 0)}")

    # Show first few letters
    for i, letter in enumerate(manifest['letters'][:5]):
        logger.info(f"  [{i+1}] {letter.get('document_number')} - {letter.get('title', 'No title')[:60]}")

    await scraper.close()
    return manifest


async def test_fns_document_fetch():
    """Test FNS document content fetching."""
    logger.info("Testing FNS document fetching...")

    # First get manifest to find a document URL
    scraper = MinistryScraper("fns")
    manifest = await scraper.fetch_manifest()

    if not manifest['letters']:
        logger.warning("No letters found in manifest, skipping document fetch test")
        await scraper.close()
        return

    # Fetch first document
    first_letter_url = manifest['letters'][0]['url']
    logger.info(f"Fetching document from: {first_letter_url}")

    doc = await scraper.fetch_document(first_letter_url)

    logger.info(f"Document fetched:")
    logger.info(f"  Doc ID: {doc.doc_id}")
    logger.info(f"  URL: {doc.url}")
    logger.info(f"  Content length: {len(doc.content)} bytes")
    logger.info(f"  Title: {doc.metadata.get('title', 'No title')[:60]}")
    logger.info(f"  Number: {doc.metadata.get('document_number', 'No number')}")
    logger.info(f"  Date: {doc.metadata.get('document_date', 'No date')}")

    await scraper.close()
    return doc


async def test_fns_letters():
    """Test FNS letters fetching."""
    logger.info("Testing FNS letters fetching (last 5 years, limit 3)...")

    scraper = MinistryScraper("fns")
    # fetch_recent_letters accepts 'years' parameter - use 5 years for more results
    letters = await scraper.fetch_recent_letters(years=5)
    letters = letters[:3]  # Limit to 3 for testing

    logger.info(f"Fetched {len(letters)} letters:")
    for i, letter in enumerate(letters):
        logger.info(f"  [{i+1}] {letter.document_number} - {letter.title[:60]}")

    await scraper.close()
    return letters


async def main():
    """Run all FNS scraper tests."""
    logger.info("=" * 60)
    logger.info("FNS Scraper Test Suite")
    logger.info("=" * 60)

    try:
        # Test 1: Manifest
        logger.info("\n--- Test 1: Manifest Fetching ---")
        await test_fns_manifest()

        # Test 2: Document fetching
        logger.info("\n--- Test 2: Document Fetching ---")
        await test_fns_document_fetch()

        # Test 3: Letters fetching
        logger.info("\n--- Test 3: Letters Fetching ---")
        await test_fns_letters()

        logger.info("\n" + "=" * 60)
        logger.info("All tests completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
