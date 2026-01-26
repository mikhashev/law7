"""
Import regional Administrative Codes (KoAP) for Phase 7C target regions.

This script imports regional KoAP data into the database following the
country_modules architecture established in Phase 7A/7B.

Target regions (Phase 7C): Top 10 by population
- Moscow, Moscow Region, Saint Petersburg
- Krasnodar, Sverdlovsk, Rostov
- Tatarstan, Bashkortostan, Novosibirsk, Nizhny Novgorod
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import date
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.db import DatabaseClient
from core.config import get_settings
from country_modules.russia.scrapers.regional_scraper import (
    RegionalScraper,
    PHASE7C_REGIONS,
    get_region_config,
    list_phase7c_regions
)

logger = logging.getLogger(__name__)


class RegionalKoapImporter:
    """
    Import regional KoAP data into the database.
    """

    def __init__(self, db: DatabaseClient):
        """
        Initialize importer.

        Args:
            db: Database client
        """
        self.db = db
        self.settings = get_settings()
        self.country_id = 1  # Russia's ID in countries table
        self.country_code = "RU"

    async def import_regional_code(self, region_key: str, koap_data: Dict[str, Any]) -> str:
        """
        Import a regional code into the database.

        Args:
            region_key: Region key (e.g., 'moscow', 'tatarstan')
            koap_data: KoAP data dict from scraper

        Returns:
            UUID of inserted/updated code record
        """
        config = get_region_config(region_key)

        # Check if code already exists
        existing = await self.db.execute(
            """
            SELECT id FROM regional_codes
            WHERE country_id = $1 AND region_id = $2 AND code_id = $3
            """,
            self.country_id, config.region_id, koap_data["code_id"]
        )

        if existing:
            # Update existing code
            code_uuid = existing[0]["id"]
            await self.db.execute(
                """
                UPDATE regional_codes
                SET code_name = $1, last_amendment_date = $2,
                    consolidation_status = $3, source_url = $4, updated_at = NOW()
                WHERE id = $5
                """,
                koap_data["code_name"],
                koap_data.get("last_amendment_date"),
                koap_data.get("consolidation_status", "pending"),
                koap_data.get("source_url"),
                code_uuid
            )
            logger.info(f"Updated regional code: {koap_data['code_id']}")
        else:
            # Insert new code
            result = await self.db.execute(
                """
                INSERT INTO regional_codes
                (country_id, country_code, region_id, region_name, code_id, code_name,
                 code_type, adoption_date, last_amendment_date, consolidation_status,
                 is_active, source_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
                """,
                self.country_id,
                self.country_code,
                config.region_id,
                config.region_name,
                koap_data["code_id"],
                koap_data["code_name"],
                "administrative",  # KoAP is administrative code
                koap_data.get("adoption_date"),
                koap_data.get("last_amendment_date"),
                koap_data.get("consolidation_status", "pending"),
                True,
                koap_data.get("source_url")
            )
            code_uuid = result[0]["id"]
            logger.info(f"Inserted regional code: {koap_data['code_id']}")

        return code_uuid

    async def import_regional_article(
        self,
        region_key: str,
        code_id: str,
        article_data: Dict[str, Any
    ]) -> str:
        """
        Import a regional code article into the database.

        Args:
            region_key: Region key
            code_id: Regional code ID (e.g., "KOAP_MOSCOW")
            article_data: Article data dict

        Returns:
            UUID of inserted/updated article record
        """
        config = get_region_config(region_key)
        article_number = article_data["article_number"]
        version_date = article_data.get("version_date", date.today())

        # Check if article version already exists
        existing = await self.db.execute(
            """
            SELECT id FROM regional_code_articles
            WHERE country_id = $1 AND region_id = $2 AND code_id = $3
              AND article_number = $4 AND version_date = $5
            """,
            self.country_id, config.region_id, code_id, article_number, version_date
        )

        if existing:
            # Update existing article
            article_uuid = existing[0]["id"]
            await self.db.execute(
                """
                UPDATE regional_code_articles
                SET article_title = $1, article_content = $2,
                    status = $3, effective_from = $4, effective_until = $5,
                    is_current = $6, source_url = $7, updated_at = NOW()
                WHERE id = $8
                """,
                article_data.get("article_title"),
                article_data["article_content"],
                article_data.get("status", "active"),
                article_data.get("effective_from"),
                article_data.get("effective_until"),
                article_data.get("is_current", True),
                article_data.get("source_url"),
                article_uuid
            )
            logger.debug(f"Updated article {code_id} {article_number}")
        else:
            # Insert new article
            result = await self.db.execute(
                """
                INSERT INTO regional_code_articles
                (country_id, country_code, region_id, code_id, article_number,
                 chapter_number, part_number, article_title, article_content,
                 status, effective_from, effective_until, version_date, is_current, source_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
                """,
                self.country_id,
                self.country_code,
                config.region_id,
                code_id,
                article_number,
                article_data.get("chapter_number"),
                article_data.get("part_number"),
                article_data.get("article_title"),
                article_data["article_content"],
                article_data.get("status", "active"),
                article_data.get("effective_from"),
                article_data.get("effective_until"),
                version_date,
                article_data.get("is_current", True),
                article_data.get("source_url")
            )
            article_uuid = result[0]["id"]
            logger.debug(f"Inserted article {code_id} {article_number}")

        return article_uuid

    async def import_region_koap(self, region_key: str, koap_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Import complete KoAP for a region (code + articles).

        Args:
            region_key: Region key
            koap_data: Complete KoAP data from scraper

        Returns:
            Dict with import statistics
        """
        stats = {
            "code": 0,
            "articles": 0,
            "errors": 0
        }

        try:
            # Import the code record
            await self.import_regional_code(region_key, koap_data)
            stats["code"] = 1

            # Import articles
            for article in koap_data.get("articles", []):
                try:
                    await self.import_regional_article(
                        region_key,
                        koap_data["code_id"],
                        article
                    )
                    stats["articles"] += 1
                except Exception as e:
                    logger.error(f"Failed to import article {article.get('article_number')}: {e}")
                    stats["errors"] += 1

            logger.info(
                f"Imported KoAP for {region_key}: "
                f"{stats['code']} code, {stats['articles']} articles, {stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Failed to import KoAP for {region_key}: {e}")
            stats["errors"] += 1

        return stats

    async def import_all_phase7c_regions(self) -> Dict[str, Dict[str, int]]:
        """
        Import KoAP for all Phase 7C target regions.

        Returns:
            Dict mapping region_key to import statistics
        """
        logger.info("Starting Phase 7C regional KoAP import")

        all_stats = {}
        scraper = RegionalScraper()

        for region_key in list_phase7c_regions():
            try:
                # Fetch KoAP data from scraper
                koap_data = await scraper.fetch_regional_koap(region_key)

                # Import to database
                stats = await self.import_region_koap(region_key, koap_data)
                all_stats[region_key] = stats

            except Exception as e:
                logger.error(f"Failed to process region {region_key}: {e}")
                all_stats[region_key] = {
                    "code": 0,
                    "articles": 0,
                    "errors": 1
                }

        # Log summary
        total_codes = sum(s["code"] for s in all_stats.values())
        total_articles = sum(s["articles"] for s in all_stats.values())
        total_errors = sum(s["errors"] for s in all_stats.values())

        logger.info(
            f"Phase 7C regional KoAP import complete: "
            f"{total_codes} codes, {total_articles} articles, {total_errors} errors"
        )

        return all_stats

    async def get_import_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on imported regional data.

        Returns:
            Dict with import statistics
        """
        # Regional codes
        codes = await self.db.execute(
            """
            SELECT region_id, region_name, code_id, code_name,
                   consolidation_status, is_active
            FROM regional_codes
            WHERE country_id = $1
            ORDER BY region_id
            """,
            self.country_id
        )

        # Regional articles
        articles = await self.db.execute(
            """
            SELECT region_id, code_id,
                   COUNT(*) as article_count,
                   COUNT(*) FILTER (WHERE is_current = true) as current_count
            FROM regional_code_articles
            WHERE country_id = $1
            GROUP BY region_id, code_id
            ORDER BY region_id
            """,
            self.country_id
        )

        return {
            "codes": codes,
            "articles": articles,
            "total_codes": len(codes),
            "total_articles": sum(row["article_count"] for row in articles)
        }


async def main():
    """Main entry point for regional KoAP import."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting regional KoAP import")

    # Initialize database
    settings = get_settings()
    db = DatabaseClient(settings)
    await db.connect()

    try:
        # Create importer
        importer = RegionalKoapImporter(db)

        # Import all Phase 7C regions
        stats = await importer.import_all_phase7c_regions()

        # Get statistics
        statistics = await importer.get_import_statistics()

        logger.info("Regional KoAP import statistics:")
        logger.info(f"  Total codes: {statistics['total_codes']}")
        logger.info(f"  Total articles: {statistics['total_articles']}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
