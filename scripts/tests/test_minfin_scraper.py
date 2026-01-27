#!/usr/bin/env python3
"""
Simple test for Ministry of Finance scraper.

Usage:
    cd scripts && python -m tests.test_minfin_scraper
"""

import asyncio
import sys
from pathlib import Path

# Ensure parent directory is in path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from country_modules.russia.scrapers.ministry_scraper import MinistryScraper
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Test Minfin scraper."""
    print("\n" + "="*70)
    print("MINFIN SCRAPER TEST")
    print("="*70)

    scraper = MinistryScraper("minfin")

    try:
        print("\nFetching manifest...")
        manifest = await scraper.fetch_manifest()

        print(f"\n✓ Success!")
        print(f"  Agency: {manifest['agency_name_short']}")
        print(f"  Letters found: {len(manifest.get('letters', []))}")
        print(f"  Last updated: {manifest['last_updated']}")

        if manifest.get('letters'):
            print(f"\n  First 3 letters:")
            for i, letter in enumerate(manifest['letters'][:3], 1):
                print(f"    {i}. {letter.get('title', 'N/A')[:60]}")
                print(f"       Date: {letter.get('document_date', 'N/A')}")
                print(f"       Number: {letter.get('document_number', 'N/A')}")
                print()

        # Test fetching a document if we have URLs
        if manifest.get('letters') and len(manifest['letters']) > 0:
            print("Testing document fetch...")
            first_url = manifest['letters'][0]['url']
            doc = await scraper.fetch_document(first_url)

            print(f"\n✓ Document fetched!")
            print(f"  URL: {doc.url}")
            print(f"  Content length: {len(doc.content)} bytes")
            print(f"  Title: {doc.metadata.get('title', 'N/A')[:100]}")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        await scraper.close()
        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
