"""
Import Supreme Court decisions for Phase 7C (vsrf.ru).

This script imports Supreme Court Plenary Resolutions into the database following
the country_modules architecture established in Phase 7A/7B.

Phase 7C scope:
- Supreme Court Plenary Resolutions (Постановления Пленума ВС РФ)
- Practice Reviews (Обзоры судебной практики)
- Presidium Resolutions (Постановления Президиума ВС РФ)

Usage:
    poetry run python scripts/country_modules/russia/import/import_supreme_court.py --year 2025 --limit 10
    poetry run python scripts/country_modules/russia/import/import_supreme_court.py --all
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import date
import sys
from pathlib import Path
import argparse

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import text
from scripts.core.db import get_db_connection
from scripts.core.config import get_settings
from country_modules.russia.scrapers.court_scraper import CourtScraper

logger = logging.getLogger(__name__)


class SupremeCourtImporter:
    """
    Import Supreme Court decisions into the database.
    """

    # Default parameters
    DEFAULT_YEAR = 2025
    DEFAULT_LIMIT = 100
    BATCH_SIZE = 20  # Smaller batches for court decisions (more content)

    def __init__(self):
        """Initialize importer."""
        self.settings = get_settings()
        self.country_id = 1  # Russia's ID in countries table
        self.country_code = "RU"

    def import_supreme_court_resolution(
        self,
        resolution: Dict[str, Any]
    ) -> str:
        """
        Import a Supreme Court resolution into the database.

        Args:
            resolution: Resolution metadata dictionary from scraper

        Returns:
            UUID of inserted/updated resolution record
        """
        with get_db_connection() as conn:
            # Check if resolution already exists
            existing = conn.execute(
                text("""
                SELECT id FROM court_decisions
                WHERE source_url = :source_url
                LIMIT 1
                """),
                {"source_url": resolution["url"]}
            )
            existing_row = existing.fetchone()

            if existing_row:
                logger.debug(f"Resolution already exists: {resolution['doc_id']}")
                return existing_row[0]

            # Insert new resolution
            result = conn.execute(
                text("""
                INSERT INTO court_decisions (
                    country_id,
                    country_code,
                    court_type,
                    decision_type,
                    case_number,
                    decision_date,
                    publication_date,
                    title,
                    summary,
                    full_text,
                    source_url,
                    created_at
                ) VALUES (
                    :country_id,
                    :country_code,
                    :court_type,
                    :decision_type,
                    :case_number,
                    :decision_date,
                    :publication_date,
                    :title,
                    :summary,
                    :full_text,
                    :source_url,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
                """),
                {
                    "country_id": self.country_id,
                    "country_code": self.country_code,
                    "court_type": "supreme",
                    "decision_type": "plenary_resolution",
                    "case_number": resolution["doc_id"],
                    "decision_date": None,  # Will be parsed from content
                    "publication_date": None,
                    "title": resolution["title"][:500],
                    "summary": resolution["title"][:500],  # Use title as summary initially
                    "full_text": "",  # Will be populated with full content
                    "source_url": resolution["url"],
                }
            )
            conn.commit()

            resolution_id = result.fetchone()[0]
            logger.info(f"Imported resolution {resolution['doc_id']}: {resolution['title'][:80]}")
            return resolution_id

    def import_batch(
        self,
        resolutions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Import a batch of resolutions.

        Args:
            resolutions: List of resolution metadata dictionaries

        Returns:
            Dictionary with import statistics
        """
        imported = 0
        skipped = 0
        failed = []

        for resolution in resolutions:
            try:
                self.import_supreme_court_resolution(resolution)
                imported += 1
            except Exception as e:
                logger.warning(f"Failed to import {resolution.get('doc_id')}: {e}")
                failed.append({"resolution": resolution, "error": str(e)})
                skipped += 1

        return {
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
        }


async def import_supreme_court_decisions(
    year: int = None,
    limit: int = None,
    use_selenium: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Import Supreme Court decisions for a given year.

    Args:
        year: Year to import (default: current year)
        limit: Maximum number of decisions to import
        use_selenium: Use Selenium WebDriver (required for vsrf.ru)
        dry_run: Parse and count without saving to database

    Returns:
        Dictionary with import statistics
    """
    if year is None:
        year = SupremeCourtImporter.DEFAULT_YEAR

    if limit is None:
        limit = SupremeCourtImporter.DEFAULT_LIMIT

    logger.info("=" * 60)
    logger.info("Supreme Court (vsrf.ru) Import")
    logger.info("=" * 60)
    logger.info(f"Year: {year}")
    logger.info(f"Limit: {limit}")
    logger.info(f"Use Selenium: {use_selenium}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("=" * 60)

    start_time = date.today()

    # Initialize scraper
    scraper = CourtScraper(court_type="supreme")

    try:
        # Fetch resolutions
        logger.info(f"\n[Step 1] Fetching Supreme Court plenary resolutions for {year}...")
        resolutions = await scraper.fetch_supreme_plenary_resolutions(
            year=year,
            limit=limit,
            use_selenium=use_selenium
        )

        logger.info(f"Fetched {len(resolutions)} resolutions")

        if not resolutions:
            logger.warning("No resolutions found for the specified parameters")
            return {
                "status": "completed",
                "year": year,
                "fetched": 0,
                "imported": 0,
                "skipped": 0,
                "dry_run": dry_run,
            }

        # Show sample
        logger.info("\n[Sample of resolutions]")
        for i, res in enumerate(resolutions[:5], 1):
            logger.info(f"  {i}. ID={res['doc_id']}, URL={res['url']}")

        if dry_run:
            logger.info(f"\n[DRY RUN] Would import {len(resolutions)} resolutions")
            return {
                "status": "completed",
                "year": year,
                "fetched": len(resolutions),
                "imported": 0,
                "skipped": 0,
                "dry_run": True,
            }

        # Import to database
        logger.info(f"\n[Step 2] Importing resolutions to database...")
        importer = SupremeCourtImporter()
        stats = importer.import_batch(resolutions)

        duration = (date.today() - start_time).days

        result = {
            "status": "completed",
            "year": year,
            "fetched": len(resolutions),
            "imported": stats["imported"],
            "skipped": stats["skipped"],
            "failed_count": len(stats["failed"]),
            "dry_run": dry_run,
            "duration_days": duration,
        }

        logger.info("\n" + "=" * 60)
        logger.info("Import completed")
        logger.info("=" * 60)
        logger.info(f"Year: {year}")
        logger.info(f"Fetched: {result['fetched']} resolutions")
        logger.info(f"Imported: {result['imported']} resolutions")
        logger.info(f"Skipped: {result['skipped']} resolutions")
        if result['failed_count'] > 0:
            logger.info(f"Failed: {result['failed_count']} resolutions")

        return result

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "year": year,
        }

    finally:
        await scraper.close()


async def main_async():
    """Async main entry point for the import script."""
    parser = argparse.ArgumentParser(
        description="Import Supreme Court decisions from vsrf.ru"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year to import (default: current year)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=f"Maximum number of decisions to import (default: {SupremeCourtImporter.DEFAULT_LIMIT})"
    )
    parser.add_argument(
        "--no-selenium",
        action="store_true",
        help="Disable Selenium (not recommended for vsrf.ru)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count without saving to database"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import all available years (2020-2025)"
    )

    args = parser.parse_args()

    # Handle --all flag
    if args.all:
        logger.info("Importing all available years (2020-2025)")
        total_stats = {
            "status": "running",
            "years": [],
            "total_imported": 0,
            "total_skipped": 0,
        }

        for year in range(2025, 2019, -1):  # 2025 down to 2020
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing year {year}")
            logger.info(f"{'='*60}")

            stats = await import_supreme_court_decisions(
                year=year,
                limit=50,  # Reasonable limit per year
                use_selenium=not args.no_selenium,
                dry_run=args.dry_run
            )

            total_stats["years"].append(stats)
            total_stats["total_imported"] += stats.get("imported", 0)
            total_stats["total_skipped"] += stats.get("skipped", 0)

            # Small delay between years
            await asyncio.sleep(3)

        total_stats["status"] = "completed"
        logger.info(f"\n{'='*60}")
        logger.info("ALL YEARS SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total imported: {total_stats['total_imported']}")
        logger.info(f"Total skipped: {total_stats['total_skipped']}")

        return 0 if total_stats["status"] == "completed" else 1

    # Run single year import
    stats = await import_supreme_court_decisions(
        year=args.year,
        limit=args.limit,
        use_selenium=not args.no_selenium,
        dry_run=args.dry_run
    )

    return 0 if stats["status"] == "completed" else 1


def main():
    """Main entry point wrapper."""
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
