"""
Test SUDRF scraper with AJAX integration.

Usage:
    poetry run python scripts/tests/test_sudrf_scraper.py
"""
import asyncio
import logging
from datetime import date, timedelta
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from country_modules.russia.scrapers.sudrf_scraper import SudrfScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_sudrf_scraper():
    """Test SUDRF scraper with AJAX integration."""
    logger.info("Testing SUDRF scraper with AJAX integration")

    # Initialize scraper
    since_date = date.today() - timedelta(days=30)  # Last 30 days
    scraper = SudrfScraper(start_date=since_date)

    try:
        # Fetch recent decisions
        decisions = await scraper._fetch_recent_decisions(
            since=since_date,
            limit=10
        )

        logger.info(f"Found {len(decisions)} decisions")

        # Display first 3 decisions
        for i, decision in enumerate(decisions[:3], 1):
            logger.info(
                f"Decision {i}: "
                f"Case={decision.get('case_number', 'N/A')[:50]}, "
                f"URL={decision.get('url', 'N/A')[:80]}"
            )

        # Test fetch_document if we have decisions
        if decisions:
            test_decision = decisions[0]
            case_id = test_decision.get('case_id')
            if case_id:
                logger.info(f"Testing fetch_document for case_id: {case_id}")
                doc = await scraper.fetch_document(case_id)
                logger.info(
                    f"Document fetched: {len(doc.content)} bytes, "
                    f"content_type={doc.content_type}"
                )

    except Exception as e:
        logger.error(f"Error testing SUDRF scraper: {e}", exc_info=True)

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(test_sudrf_scraper())
