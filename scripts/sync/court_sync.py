"""
Court decision sync script for Law7 (Russia).

Fetches court decisions from pravo.gov.ru and stores them in the database.
Follows AI_WORKFLOW.md guidelines for batch operations and performance.

This is the initial implementation for Phase 1 (Foundation) of the court
decision fetching feature.

Usage:
    poetry run python scripts/sync/court_sync.py --start-date 2022-01-01 --end-date 2024-12-31
    poetry run python scripts/sync/court_sync.py --last-days 30
    poetry run python scripts/sync/court_sync.py --test --limit 10
"""
import argparse
import hashlib
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from country_modules.russia.scrapers.pravo_api_client import PravoApiClient
from country_modules.russia.parsers.court_decision_parser import CourtDecisionParser
from country_modules.russia.parsers.html_parser import PravoContentParser
from core.config import PRAVO_API_TIMEOUT
from core.db import get_db_connection
from utils.progress import ProgressTracker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants following AI_WORKFLOW.md batch operations guidelines
BATCH_SIZE = 500  # Optimal batch size for PostgreSQL
RATE_LIMIT_DELAY = 10  # Seconds per 100 documents (respectful rate limiting)

# Russia country ID (from countries table)
COUNTRY_ID = 1  # Russia has id=1 in the countries table


class CourtSyncService:
    """
    Service for syncing court decisions from pravo.gov.ru (Russia).

    This is the initial implementation for Phase 1:
    - Uses pravo.gov.ru API (official source)
    - Focuses on Constitutional Court decisions
    - Last 2 years scope (2022-2024)

    Future phases will add:
    - kad_scraper.py for arbitration courts
    - sudrf_scraper.py for general jurisdiction
    - vsrf/ksrf scrapers for supreme/constitutional courts
    """

    country_id = "RUS"
    country_name = "Russia"

    def __init__(
        self,
        batch_size: int = BATCH_SIZE,
        rate_limit_delay: int = RATE_LIMIT_DELAY,
        dry_run: bool = False,
    ):
        """
        Initialize the court sync service.

        Args:
            batch_size: Number of documents per batch (default: 500)
            rate_limit_delay: Seconds to wait per 100 docs (default: 10s)
            dry_run: If True, don't save to database
        """
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay
        self.dry_run = dry_run
        self.api_client = PravoApiClient()
        self.parser = CourtDecisionParser()
        self.content_parser = PravoContentParser(use_ocr=False)  # For fetching full HTML
        self.progress = ProgressTracker()

    def run(
        self,
        start_date: str,
        end_date: str,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run the court sync process.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            limit: Maximum number of decisions to fetch (for testing)

        Returns:
            Dictionary with sync statistics

        Example:
            >>> service = CourtSyncService()
            >>> stats = service.run(start_date="2022-01-01", end_date="2024-12-31")
            >>> print(f"Synced {stats['total_decisions']} decisions")
        """
        logger.info("="*60)
        logger.info("Law7 Court Decision Sync Service")
        logger.info("="*60)
        logger.info(f"Country: {self.country_name}")
        logger.info(f"Start date: {start_date}")
        logger.info(f"End date: {end_date}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Rate limit: {self.rate_limit_delay}s per 100 docs")
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
            # Fetch court decisions from pravo.gov.ru API
            logger.info("\n[Step 1] Fetching court decisions from pravo.gov.ru API...")
            decisions = self.api_client.get_court_decisions(
                start_date=start_date,
                end_date=end_date,
            )

            if limit:
                decisions = decisions[:limit]

            logger.info(f"Fetched {len(decisions)} court decisions")

            if not decisions:
                logger.warning("No court decisions found for the specified date range")
                stats["status"] = "completed"
                return stats

            # Parse and store decisions in batches
            logger.info("\n[Step 2] Parsing and storing decisions...")
            total_decisions, total_article_refs = self._sync_decisions_batched(decisions)

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

    def _sync_decisions_batched(
        self,
        decisions: List[Dict[str, Any]],
    ) -> tuple[int, int]:
        """
        Sync decisions to database in batches.

        Follows AI_WORKFLOW.md batch operations guidelines:
        - Batch size of 500 for optimal PostgreSQL performance
        - Single commit per batch
        - Rate limiting between batches

        Args:
            decisions: List of decision data from API

        Returns:
            Tuple of (total_decisions_synced, total_article_refs_synced)
        """
        total_decisions = 0
        total_article_refs = 0

        for batch_start in range(0, len(decisions), self.batch_size):
            batch = decisions[batch_start:batch_start + self.batch_size]
            batch_num = batch_start // self.batch_size + 1
            total_batches = (len(decisions) + self.batch_size - 1) // self.batch_size

            logger.info(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} decisions)...")

            # Prepare batch data
            decisions_data = []
            article_refs_data = []

            for doc in batch:
                try:
                    # Fetch full HTML content using Selenium (Phase 2 enhancement)
                    eo_number = doc.get('eoNumber', '')
                    full_text = doc.get('name', '')  # Fallback to metadata

                    if eo_number:
                        logger.debug(f"Fetching full HTML for {eo_number}...")
                        html_content = self.content_parser.fetch_with_selenium(eo_number)
                        if html_content and len(html_content) > 100:
                            full_text = html_content
                            logger.debug(f"Fetched {len(html_content)} chars from Selenium")
                        else:
                            logger.debug(f"Selenium returned no content, using metadata")

                    # Parse decision with full text
                    parsed = self.parser.parse_court_decision({'full_text': full_text})

                    # Generate text hash
                    text_hash = parsed['text_hash']

                    # Prepare decision data
                    decision_data = {
                        'country_id': COUNTRY_ID,
                        'country_code': 'RU',
                        'court_type': 'constitutional',  # pravo.gov.ru mostly has Constitutional Court
                        'decision_type': 'ruling',  # Default type
                        'case_number': eo_number or doc.get('id', doc.get('documentNumber', '')),
                        'decision_date': doc.get('documentDate'),
                        'publication_date': doc.get('publishDate'),
                        'title': doc.get('title', ''),
                        'summary': parsed['summary'],
                        'full_text': full_text,
                        'text_hash': text_hash,
                        'source_url': f"http://publication.pravo.gov.ru/Document/View/{eo_number}",
                        'source_type': 'pravo_api_selenium' if html_content else 'pravo_api',
                    }
                    decisions_data.append(decision_data)

                    # Prepare article references
                    decision_id = text_hash  # Temporary ID, will be replaced with actual UUID
                    for ref in parsed['article_references']:
                        article_refs_data.append({
                            'court_decision_id': decision_id,
                            'code_id': ref['code_id'],
                            'article_number': ref['article_number'],
                            'reference_context': ref['reference_context'],
                            'reference_type': ref['reference_type'],
                            'position_in_text': ref['position_in_text'],
                        })

                    # Add delay after Selenium fetch (Selenium is slower)
                    if html_content:
                        import time
                        time.sleep(2)  # 2 second delay per Selenium fetch

                except Exception as e:
                    logger.warning(f"Failed to parse decision {doc.get('eoNumber', 'unknown')}: {e}")
                    continue

            # Store batch in database
            if not self.dry_run:
                batch_synced, batch_refs = self._save_batch_to_db(decisions_data, article_refs_data)
                total_decisions += batch_synced
                total_article_refs += batch_refs
            else:
                logger.info(f"[DRY RUN] Would save {len(decisions_data)} decisions with {len(article_refs_data)} article refs")
                total_decisions += len(decisions_data)
                total_article_refs += len(article_refs_data)

            # Rate limiting between batches (if not last batch)
            if batch_num < total_batches:
                delay = (len(batch) // 100) * self.rate_limit_delay
                logger.info(f"Rate limiting: sleeping {delay}s...")
                import time
                time.sleep(delay)

        return total_decisions, total_article_refs

    def _save_batch_to_db(
        self,
        decisions_data: List[Dict[str, Any]],
        article_refs_data: List[Dict[str, Any]],
    ) -> tuple[int, int]:
        """
        Save a batch of decisions and article references to database.

        Uses batch INSERT with executemany for optimal performance
        (per AI_WORKFLOW.md guidelines).

        Args:
            decisions_data: List of decision records
            article_refs_data: List of article reference records

        Returns:
            Tuple of (decisions_saved, article_refs_saved)
        """
        from sqlalchemy import text

        with get_db_connection() as conn:
            # Insert court_decisions
            decision_query = text("""
                INSERT INTO court_decisions (
                    country_id, country_code, court_type, decision_type,
                    case_number, decision_date, publication_date, title,
                    summary, full_text, text_hash, source_url, source_type
                ) VALUES (
                    :country_id, :country_code, :court_type, :decision_type,
                    :case_number, :decision_date, :publication_date, :title,
                    :summary, :full_text, :text_hash, :source_url, :source_type
                )
                ON CONFLICT (case_number) DO NOTHING
                RETURNING id
            """)

            # Execute batch insert for decisions
            result = conn.execute(decision_query, decisions_data)
            decision_ids = [row[0] for row in result]
            conn.commit()

            logger.info(f"Saved {len(decision_ids)} court decisions")

            # Now insert article references with actual decision IDs
            if decision_ids and article_refs_data:
                # Map decision hashes to actual IDs
                # We need to re-fetch the decisions to get their actual IDs
                ref_query = text("""
                    INSERT INTO court_decision_article_references (
                        court_decision_id, code_id, article_number,
                        reference_context, reference_type, position_in_text
                    )
                    SELECT cd.id, :code_id, :article_number, :reference_context, :reference_type, :position_in_text
                    FROM court_decisions cd
                    WHERE cd.text_hash = (
                        SELECT text_hash FROM court_decisions
                        WHERE id = :decision_id_limit
                        LIMIT 1
                    )
                """)

                # For simplicity, let's use a direct approach with JOIN
                refs_inserted = 0
                for i, ref_data in enumerate(article_refs_data):
                    if i >= len(decision_ids):
                        break
                    ref_data['court_decision_id'] = decision_ids[i]

                # Batch insert article references
                refs_query = text("""
                    INSERT INTO court_decision_article_references (
                        court_decision_id, code_id, article_number,
                        reference_context, reference_type, position_in_text
                    ) VALUES (
                        :court_decision_id, :code_id, :article_number,
                        :reference_context, :reference_type, :position_in_text
                    )
                """)
                conn.execute(refs_query, article_refs_data[:len(decision_ids)])
                conn.commit()

                refs_inserted = len(article_refs_data[:len(decision_ids)])
                logger.info(f"Saved {refs_inserted} article references")
            else:
                refs_inserted = 0

            return len(decision_ids), refs_inserted


def main():
    """Main entry point for the court sync script."""
    parser = argparse.ArgumentParser(
        description="Sync court decisions from pravo.gov.ru to Law7 database"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--last-days",
        type=int,
        help="Fetch decisions from last N days",
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
        help="Test mode with small dataset (implies --limit 10 --dry-run)",
    )

    args = parser.parse_args()

    # Handle test mode
    if args.test:
        args.limit = 10
        args.dry_run = True

    # Calculate date range
    if args.last_days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.last_days)
    elif args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else datetime.now()
    else:
        # Default: last 2 years
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)  # 2 years

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # Run sync
    service = CourtSyncService(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    stats = service.run(
        start_date=start_date_str,
        end_date=end_date_str,
        limit=args.limit,
    )

    # Exit with appropriate code
    sys.exit(0 if stats["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
