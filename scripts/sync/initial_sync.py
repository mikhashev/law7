"""
Initial sync script for law7.
Fetches all documents from pravo.gov.ru and stores them in the database.
Based on ygbis patterns for batch processing and error handling.
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.pravo_api_client import PravoApiClient
from core.config import INITIAL_SYNC_BLOCK, INITIAL_SYNC_START_DATE, SYNC_BATCH_SIZE
from core.db import check_db_connection
from indexer.postgres_indexer import PostgresIndexer
from utils.progress import ProgressTracker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class InitialSyncService:
    """
    Service for performing initial sync of documents from pravo.gov.ru.
    Fetches documents by date range and stores them in the database.
    """

    def __init__(self, batch_size: int = SYNC_BATCH_SIZE):
        """
        Initialize the sync service.

        Args:
            batch_size: Number of documents to process per batch
        """
        self.batch_size = batch_size
        self.api_client = PravoApiClient()
        self.indexer = PostgresIndexer(batch_size=batch_size)
        self.progress = ProgressTracker()

    def run(
        self,
        start_date: str = None,
        end_date: str = None,
        block: str = None,
    ) -> dict:
        """
        Run the initial sync process.

        Args:
            start_date: Start date in YYYY-MM-DD format (default: from config)
            end_date: End date in YYYY-MM-DD format (default: today)
            block: Publication block code to filter (default: from config)

        Returns:
            Dictionary with sync statistics

        Example:
            >>> service = InitialSyncService()
            >>> stats = service.run(start_date="2024-01-01", end_date="2024-01-31")
            >>> print(f"Synced {stats['total_documents']} documents")
        """
        start_date = start_date or INITIAL_SYNC_START_DATE
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        block = block or INITIAL_SYNC_BLOCK

        logger.info("="*60)
        logger.info("Law7 Initial Sync Service")
        logger.info("="*60)
        logger.info(f"Start date: {start_date}")
        logger.info(f"End date: {end_date}")
        logger.info(f"Block: {block if block != 'all' else 'All blocks'}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info("="*60)

        start_time = datetime.now()
        stats = {
            "start_time": start_time,
            "start_date": start_date,
            "end_date": end_date,
            "block": block,
            "total_documents": 0,
            "total_pages": 0,
            "errors": [],
            "status": "running",
        }

        try:
            # Step 1: Check database connection
            logger.info("\n[Step 1] Checking database connection...")
            if not check_db_connection():
                raise Exception("Cannot connect to database")

            # Step 2: Sync reference data (signatory authorities, document types)
            logger.info("\n[Step 2] Syncing reference data...")
            self._sync_reference_data()

            # Step 3: Stream and sync documents by date range (in batches)
            logger.info("\n[Step 3] Syncing documents (streaming mode)...")
            total_documents, total_upserted = self._stream_sync_documents(
                start_date=start_date,
                end_date=end_date,
                block=block if block != "all" else None,
            )

            if total_documents == 0:
                logger.warning("No documents found for the specified date range")
                stats["status"] = "completed"
                return stats

            stats["total_documents"] = total_documents
            stats["upserted_count"] = total_upserted

            duration = (datetime.now() - start_time).total_seconds()
            stats["duration_seconds"] = duration
            stats["status"] = "completed"

            logger.info("\n" + "="*60)
            logger.info("Sync completed successfully")
            logger.info(f"Total documents: {total_documents}")
            logger.info(f"Upserted: {total_upserted}")
            logger.info(f"Duration: {duration:.1f}s")
            logger.info(f"Rate: {total_documents/duration:.1f} docs/sec")
            logger.info("="*60)

            return stats

        except KeyboardInterrupt:
            logger.warning("\nSync interrupted by user")
            stats["status"] = "interrupted"
            stats["duration_seconds"] = (datetime.now() - start_time).total_seconds()
            return stats

        except Exception as e:
            logger.error(f"\nSync failed: {e}", exc_info=True)
            stats["status"] = "failed"
            stats["error"] = str(e)
            stats["duration_seconds"] = (datetime.now() - start_time).total_seconds()
            return stats

        finally:
            self.api_client.close()

    def _stream_sync_documents(
        self,
        start_date: str,
        end_date: str,
        block: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Stream documents from API and upsert in batches.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            block: Publication block code to filter

        Returns:
            Tuple of (total_documents_fetched, total_upserted)
        """
        all_documents = []
        page = 1
        total_fetched = 0
        total_upserted = 0
        batch_buffer = []

        logger.info(f"Fetching documents from {start_date} to {end_date}")

        while True:
            # Fetch a page of documents
            result = self.api_client.search_documents(
                page=page,
                page_size=self.batch_size,
                start_date=start_date,
                end_date=end_date,
                block=block,
            )

            documents = result.get("items", [])
            if not documents:
                break

            total_fetched += len(documents)
            batch_buffer.extend(documents)

            # Log progress
            if page % 10 == 0 or page == 1:
                logger.info(f"  Fetched page {page}: {len(documents)} documents (total: {total_fetched})")

            # Upsert when buffer reaches batch size
            while len(batch_buffer) >= self.batch_size:
                batch = batch_buffer[:self.batch_size]
                batch_buffer = batch_buffer[self.batch_size:]

                upserted = self.indexer.batch_upsert_documents(batch)
                total_upserted += upserted

                logger.debug(f"  Upserted batch: {upserted} documents (progress: {total_upserted}/{total_fetched})")

            # Check if we've fetched all pages
            total_pages = result.get("pagesTotalCount", 1)
            if page >= total_pages:
                break

            page += 1

        # Upsert remaining documents in buffer
        if batch_buffer:
            upserted = self.indexer.batch_upsert_documents(batch_buffer)
            total_upserted += upserted

        logger.info(f"Total documents fetched: {total_fetched}")
        logger.info(f"Total documents upserted: {total_upserted}")

        return total_fetched, total_upserted

    def _sync_reference_data(self):
        """Sync reference data (signatory authorities, document types, etc.)."""
        try:
            # Sync signatory authorities
            logger.info("  Syncing signatory authorities...")
            authorities = self.api_client.get_signatory_authorities()
            if authorities:
                self.indexer.batch_upsert_signatory_authorities(authorities)
                logger.info(f"  Synced {len(authorities)} signatory authorities")

            # Sync document types
            logger.info("  Syncing document types...")
            doc_types = self.api_client.get_document_types()
            if doc_types:
                self.indexer.batch_upsert_document_types(doc_types)
                logger.info(f"  Synced {len(doc_types)} document types")

        except Exception as e:
            logger.warning(f"Failed to sync reference data: {e}")
            # Continue anyway, as documents can be synced without reference data


def run_daily_sync():
    """
    Run daily sync (documents from the last day).

    This is intended to be run via cron/scheduler.
    """
    logger.info("Starting daily sync...")

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    service = InitialSyncService()
    stats = service.run(start_date=yesterday, end_date=today)

    if stats["status"] == "completed":
        logger.info(f"Daily sync completed: {stats.get('upserted_count', 0)} documents")
    else:
        logger.error(f"Daily sync failed: {stats.get('status')}")

    return stats


def main():
    """Main entry point for initial sync."""
    import argparse

    parser = argparse.ArgumentParser(description="Law7 initial sync")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--block", help="Publication block code")
    parser.add_argument("--batch-size", type=int, default=SYNC_BATCH_SIZE, help="Batch size")
    parser.add_argument("--daily", action="store_true", help="Run daily sync (yesterday to today)")

    args = parser.parse_args()

    if args.daily:
        return run_daily_sync()

    service = InitialSyncService(batch_size=args.batch_size)
    stats = service.run(
        start_date=args.start_date,
        end_date=args.end_date,
        block=args.block,
    )

    # Exit with appropriate code
    if stats["status"] == "completed":
        sys.exit(0)
    elif stats["status"] == "interrupted":
        sys.exit(130)  # Standard exit code for SIGINT
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
