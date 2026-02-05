"""
Test Supreme Court (vsrf.ru) scraper for Plenary Resolutions.

Usage:
    poetry run python scripts/tests/test_vsrf_scraper.py
"""
import asyncio
import logging
import json
from datetime import date
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from country_modules.russia.scrapers.court_scraper import CourtScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_vsrf_scraper():
    """Test Supreme Court (vsrf.ru) scraper with Selenium."""
    logger.info("Testing Supreme Court (vsrf.ru) scraper with Selenium")

    # Initialize scraper for Supreme Court
    scraper = CourtScraper(court_type="supreme")

    try:
        # Test multiple years to find documents
        years = [2025, 2024, 2023]
        all_resolutions = []

        for year in years:
            logger.info(f"\n=== Testing year {year} ===")
            resolutions = await scraper.fetch_supreme_plenary_resolutions(
                year=year,
                limit=10
            )

            logger.info(f"Found {len(resolutions)} plenary resolutions for {year}")

            for i, resolution in enumerate(resolutions, 1):
                logger.info(
                    f"Resolution {i}: "
                    f"ID={resolution.get('doc_id', 'N/A')}, "
                    f"Title={resolution.get('title', 'N/A')[:80]}, "
                    f"URL={resolution.get('url', 'N/A')[:80]}"
                )

            all_resolutions.extend(resolutions)

            # Small delay between years
            await asyncio.sleep(2)

        logger.info(f"\n=== TOTAL: Found {len(all_resolutions)} resolutions across all years ===")

        # Save results to JSON for inspection
        if all_resolutions:
            output_path = Path(__file__).parent / "vsrf_results.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_resolutions, f, ensure_ascii=False, indent=2)
            logger.info(f"Results saved to {output_path}")

    except Exception as e:
        logger.error(f"Error testing vsrf scraper: {e}", exc_info=True)

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(test_vsrf_scraper())
