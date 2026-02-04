"""
SUDRF court decisions sync script for Law7 (Russia).

Fetches court decisions from sudrf.ru (general jurisdiction courts) and stores
them in the database.

Usage:
    poetry run python scripts/sync/sudrf_sync.py --limit 10 --test
    poetry run python scripts/sync/sudrf_sync.py --start-date 2022-01-01 --end-date 2024-12-31

Note: This is Phase 4 implementation for comprehensive court decision fetching.
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from country_modules.russia.scrapers.sudrf_scraper import SudrfScraper, fetch_court_decisions
from country_modules.russia.parsers.court_decision_parser import CourtDecisionParser
from core.db import get_db_connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 100  # SUDRF has rate limits, use smaller batches
RATE_LIMIT_DELAY = 10  # 10 seconds per batch
COUNTRY_ID = 1  # Russia has id=1 in the countries table


class SudrfSyncService:
    """
    Service for syncing court decisions from sudrf.ru (Russia).

    This service handles general jurisdiction court decisions including:
    - Civil cases
    - Criminal cases
    - Administrative cases
    """

    country_id = "RUS"
    country_name = "Russia"

    def __init__(
        self,
        batch_size: int = BATCH_SIZE,
        dry_run: bool = False,
    ):
        """
        Initialize the SUDRF sync service.

        Args:
            batch_size: Number of documents per batch
            dry_run: If True, don't save to database
        """
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.parser = CourtDecisionParser()

    async def run(
        self,
        start_date: str,
        end_date: str,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run the SUDRF sync process.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            limit: Maximum number of decisions to fetch

        Returns:
            Dictionary with sync statistics

        Example:
            >>> service = SudrfSyncService()
            >>> stats = await service.run(start_date="2022-01-01", end_date="2024-12-31", limit=10)
            >>> print(f"Synced {stats['total_decisions']} decisions")
        """
        logger.info("="*60)
        logger.info("Law7 SUDRF Court Decision Sync Service")
        logger.info("="*60)
        logger.info(f"Country: {self.country_name}")
        logger.info(f"Source: sudrf.ru (General Jurisdiction)")
        logger.info(f"Start date: {start_date}")
        logger.info(f"End date: {end_date}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("="*60)

        start_time = datetime.now()
        stats = {
            "start_time": start_time,
            "start_date": start_date,
            "end_date": end_date,
            "total_decisions": 0,
            "total_article_refs": 0,
            "errors": [],
            "status": "running",
        }

        try:
            # Fetch court decisions
            logger.info("\n[Step 1] Fetching court decisions from sudrf.ru...")
            decisions = await fetch_court_decisions(
                start_date=start_date,
                end_date=end_date
            )

            if limit:
                decisions = decisions[:limit]

            logger.info(f"Fetched {len(decisions)} court decisions")

            if not decisions:
                logger.warning("No court decisions found for the specified date range")
                stats["status"] = "completed"
                return stats

            # Process and store decisions
            logger.info("\n[Step 2] Processing and storing decisions...")
            total_decisions, total_article_refs = await self._process_decisions(decisions)

            stats["total_decisions"] = total_decisions
            stats["total_article_refs"] = total_article_refs

            duration = (datetime.now() - start_time).total_seconds()
            stats["duration_seconds"] = duration
            stats["status"] = "completed"

            logger.info("\n" + "="*60)
            logger.info("Sync completed successfully")
            logger.info("="*60)
            logger.info(f"Total decisions: {total_decisions}")
            logger.info(f"Total article references: {total_article_refs}")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            stats["status"] = "failed"
            stats["error"] = str(e)

        return stats

    async def _process_decisions(
        self,
        decisions: List[Any],
    ) -> tuple[int, int]:
        """
        Process decisions and store to database.

        Args:
            decisions: List of CourtDecision objects

        Returns:
            Tuple of (total_decisions_synced, total_article_refs_synced)
        """
        total_decisions = 0
        total_article_refs = 0

        for decision in decisions:
            try:
                # Parse article references from decision text
                parsed = self.parser.parse_court_decision({
                    'full_text': decision.full_text
                })

                # Prepare decision data for database
                decision_data = {
                    'country_id': COUNTRY_ID,
                    'country_code': 'RU',
                    'court_type': 'general',  # SUDRF is general jurisdiction
                    'decision_type': decision.decision_type,
                    'case_number': decision.case_number,
                    'decision_date': decision.decision_date,
                    'publication_date': decision.decision_date,
                    'title': decision.title,
                    'summary': parsed['summary'],
                    'full_text': decision.full_text,
                    'text_hash': parsed['text_hash'],
                    'source_url': decision.source_url,
                    'source_type': 'sudrf_scraper',
                }

                # Store to database
                if not self.dry_run:
                    saved_id = self._save_decision_to_db(decision_data)
                    if saved_id:
                        total_decisions += 1

                        # Save article references
                        refs_count = self._save_article_refs_to_db(
                            saved_id, parsed['article_references']
                        )
                        total_article_refs += refs_count
                else:
                    logger.info(f"[DRY RUN] Would save decision: {decision.case_number[:50]}...")

            except Exception as e:
                logger.warning(f"Failed to process decision {decision.case_number}: {e}")
                stats["errors"].append(str(e))

            # Rate limiting
            await asyncio.sleep(2)  # 2 second delay per decision

        return total_decisions, total_article_refs

    def _save_decision_to_db(self, decision_data: Dict[str, Any]) -> Optional[str]:
        """
        Save a single court decision to database.

        Args:
            decision_data: Decision data dictionary

        Returns:
            Inserted decision ID or None
        """
        from sqlalchemy import text

        try:
            with get_db_connection() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO court_decisions (
                            country_id, country_code, court_type, decision_type,
                            case_number, decision_date, publication_date, title,
                            summary, full_text, text_hash, source_url, source_type
                        ) VALUES (
                            :country_id, :country_code, :court_type, :decision_type,
                            :case_number, :decision_date, :publication_date, :title,
                            :summary, :full_text, :text_hash, :source_url, :source_type
                        )
                        ON CONFLICT (case_number) DO UPDATE SET
                            full_text = EXCLUDED.full_text,
                            summary = EXCLUDED.summary,
                            updated_at = NOW()
                        RETURNING id
                    """),
                    decision_data
                )
                conn.commit()

                if result:
                    return result.scalar()
                return None

        except Exception as e:
            logger.error(f"Failed to save decision: {e}")
            return None

    def _save_article_refs_to_db(
        self,
        decision_id: str,
        article_refs: List[Dict[str, Any]]
    ) -> int:
        """
        Save article references to database.

        Args:
            decision_id: Court decision ID (UUID)
            article_refs: List of article reference dictionaries

        Returns:
            Number of article references saved
        """
        if not article_refs:
            return 0

        from sqlalchemy import text

        try:
            with get_db_connection() as conn:
                count = 0
                for ref in article_refs:
                    conn.execute(
                        text("""
                            INSERT INTO court_decision_article_references (
                                court_decision_id, code_id, article_number,
                                reference_context, reference_type, position_in_text
                            ) VALUES (
                                :court_decision_id, :code_id, :article_number,
                                :reference_context, :reference_type, :position_in_text
                            )
                            ON CONFLICT DO NOTHING
                        """),
                        {
                            'court_decision_id': decision_id,
                            'code_id': ref['code_id'],
                            'article_number': ref['article_number'],
                            'reference_context': ref.get('reference_context', ''),
                            'reference_type': ref.get('reference_type', 'cited'),
                            'position_in_text': ref.get('position_in_text'),
                        }
                    )
                    count += 1

                conn.commit()
                return count

        except Exception as e:
            logger.error(f"Failed to save article references: {e}")
            return 0


async def main():
    """Main entry point for the SUDRF sync script."""
    parser = argparse.ArgumentParser(
        description="Sync court decisions from sudrf.ru to Law7 database"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of decisions to fetch (for testing)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Batch size for database operations (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count decisions without saving to database",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode with small dataset (implies --limit 3 --dry-run)",
    )

    args = parser.parse_args()

    # Handle test mode
    if args.test:
        args.limit = 3
        args.dry_run = True

    # Calculate date range (last 2 years if not specified)
    if not args.start_date:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)  # 2 years
        args.start_date = start_date.strftime("%Y-%m-%d")
        args.end_date = end_date.strftime("%Y-%m-%d")

    # Run sync
    service = SudrfSyncService(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    stats = await service.run(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )

    # Exit with appropriate code
    sys.exit(0 if stats["status"] == "completed" else 1)


if __name__ == "__main__":
    asyncio.run(main())
