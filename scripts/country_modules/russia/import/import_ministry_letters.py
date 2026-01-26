"""
Import ministry interpretations for Phase 7C (Minfin, FNS, Rostrud).

This script imports ministry letter data into the database following the
country_modules architecture established in Phase 7A/7B.

Phase 7C scope:
- Ministry of Finance (Минфин) - tax law interpretations (last 5 years)
- Federal Tax Service (ФНС) - tax procedure clarifications (last 5 years)
- Rostrud - labor law interpretations (last 5 years)
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import date
import sys
from pathlib import Path
import json

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.db import DatabaseClient
from core.config import get_settings
from country_modules.russia.scrapers.ministry_scraper import (
    MinistryScraper,
    MinistryLetter,
    list_phase7c_agencies,
    fetch_all_phase7c_letters,
)

logger = logging.getLogger(__name__)


class MinistryLetterImporter:
    """
    Import ministry letter data into the database.
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

    async def get_agency_id(self, agency_name_short: str) -> Optional[str]:
        """
        Get agency UUID from database by short name.

        Args:
            agency_name_short: Agency short name (e.g., "Минфин")

        Returns:
            Agency UUID or None if not found
        """
        result = await self.db.execute(
            """
            SELECT id FROM government_agencies
            WHERE country_id = $1 AND agency_name_short = $2
            """,
            self.country_id,
            agency_name_short
        )

        return result[0]["id"] if result else None

    async def import_ministry_letter(self, letter: MinistryLetter) -> str:
        """
        Import a ministry letter into the database.

        Args:
            letter: MinistryLetter object

        Returns:
            UUID of inserted/updated letter record
        """
        # Get agency UUID
        agency_id = await self.get_agency_id(letter.agency_name_short)
        if not agency_id:
            raise ValueError(f"Agency not found: {letter.agency_name_short}")

        # Check if letter already exists
        existing = await self.db.execute(
            """
            SELECT id FROM official_interpretations
            WHERE country_id = $1 AND agency_id = $2
              AND document_number = $3 AND document_date = $4
            """,
            self.country_id,
            agency_id,
            letter.document_number,
            letter.document_date
        )

        related_laws_json = (
            json.dumps(letter.related_laws) if letter.related_laws else None
        )

        if existing:
            # Update existing letter
            letter_uuid = existing[0]["id"]
            await self.db.execute(
                """
                UPDATE official_interpretations
                SET title = $1, question = $2, answer = $3,
                    full_content = $4, legal_topic = $5,
                    related_laws = $6, binding_nature = $7,
                    source_url = $8, validity_status = 'valid',
                    updated_at = NOW()
                WHERE id = $9
                """,
                letter.title,
                letter.question,
                letter.answer,
                letter.full_content,
                letter.legal_topic,
                related_laws_json,
                letter.binding_nature,
                letter.source_url,
                letter_uuid
            )
            logger.debug(f"Updated ministry letter: {letter.document_number}")
        else:
            # Insert new letter
            result = await self.db.execute(
                """
                INSERT INTO official_interpretations
                (country_id, country_code, agency_id, document_type,
                 document_number, document_date, title, question, answer,
                 full_content, legal_topic, related_laws, binding_nature,
                 validity_status, source_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
                """,
                self.country_id,
                self.country_code,
                agency_id,
                letter.document_type,
                letter.document_number,
                letter.document_date,
                letter.title,
                letter.question,
                letter.answer,
                letter.full_content,
                letter.legal_topic,
                related_laws_json,
                letter.binding_nature,
                "valid",
                letter.source_url
            )
            letter_uuid = result[0]["id"]
            logger.info(f"Inserted ministry letter: {letter.document_number}")

        return letter_uuid

    async def import_agency_letters(
        self,
        agency_key: str,
        letters: List[MinistryLetter]
    ) -> Dict[str, int]:
        """
        Import letters from a specific agency.

        Args:
            agency_key: Agency key (e.g., 'minfin', 'fns', 'rostrud')
            letters: List of MinistryLetter objects

        Returns:
            Dict with import statistics
        """
        stats = {
            "letters": 0,
            "errors": 0
        }

        for letter in letters:
            try:
                await self.import_ministry_letter(letter)
                stats["letters"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to import letter {letter.document_number}: {e}"
                )
                stats["errors"] += 1

        return stats

    async def import_all_phase7c_letters(
        self,
        years: int = 5
    ) -> Dict[str, Dict[str, int]]:
        """
        Import letters from all Phase 7C target agencies.

        Args:
            years: Number of years back to import (Phase 7C: 5 years)

        Returns:
            Dict mapping agency_key to import statistics
        """
        logger.info(f"Starting Phase 7C ministry letters import (last {years} years)")

        # Fetch letters from all agencies
        all_letters = await fetch_all_phase7c_letters(years=years)

        # Import letters
        all_stats = {}
        for agency_key, letters in all_letters.items():
            try:
                stats = await self.import_agency_letters(agency_key, letters)
                all_stats[agency_key] = stats
                logger.info(
                    f"Imported {stats['letters']} letters from {agency_key}"
                )
            except Exception as e:
                logger.error(f"Failed to import letters from {agency_key}: {e}")
                all_stats[agency_key] = {"letters": 0, "errors": 1}

        # Log summary
        total_letters = sum(s["letters"] for s in all_stats.values())
        total_errors = sum(s["errors"] for s in all_stats.values())

        logger.info(
            f"Phase 7C ministry letters import complete: "
            f"{total_letters} letters, {total_errors} errors"
        )

        return all_stats

    async def get_import_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on imported ministry letter data.

        Returns:
            Dict with import statistics
        """
        # Letters by agency
        letters_by_agency = await self.db.execute(
            """
            SELECT
                ga.agency_name_short,
                oi.document_type,
                COUNT(*) as letter_count,
                COUNT(*) FILTER (WHERE oi.validity_status = 'valid') as valid_count
            FROM official_interpretations oi
            JOIN government_agencies ga ON oi.agency_id = ga.id
            WHERE oi.country_id = $1
            GROUP BY ga.agency_name_short, oi.document_type
            ORDER BY ga.agency_name_short, oi.document_type
            """,
            self.country_id
        )

        # Letters by topic
        letters_by_topic = await self.db.execute(
            """
            SELECT
                legal_topic,
                COUNT(*) as letter_count
            FROM official_interpretations
            WHERE country_id = $1 AND legal_topic IS NOT NULL
            GROUP BY legal_topic
            ORDER BY letter_count DESC
            """,
            self.country_id
        )

        # Total counts
        total_result = await self.db.execute(
            """
            SELECT
                COUNT(*) as total_letters,
                COUNT(*) FILTER (WHERE validity_status = 'valid') as valid_letters,
                COUNT(DISTINCT agency_id) as agency_count
            FROM official_interpretations
            WHERE country_id = $1
            """,
            self.country_id
        )

        return {
            "by_agency": letters_by_agency,
            "by_topic": letters_by_topic,
            "totals": total_result[0] if total_result else {},
        }


async def main():
    """Main entry point for ministry letters import."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting ministry letters import")

    # Initialize database
    settings = get_settings()
    db = DatabaseClient(settings)
    await db.connect()

    try:
        # Create importer
        importer = MinistryLetterImporter(db)

        # Import all Phase 7C letters (last 5 years)
        stats = await importer.import_all_phase7c_letters(years=5)

        # Get statistics
        statistics = await importer.get_import_statistics()

        logger.info("Ministry letters import statistics:")
        logger.info(f"  Total letters: {statistics['totals'].get('total_letters', 0)}")
        logger.info(f"  Valid letters: {statistics['totals'].get('valid_letters', 0)}")
        logger.info(f"  Agencies: {statistics['totals'].get('agency_count', 0)}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
