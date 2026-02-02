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
import argparse

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import text
from scripts.core.db import get_db_connection
from scripts.core.config import get_settings
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

    def __init__(self):
        """Initialize importer."""
        self.settings = get_settings()
        self.country_id = 1  # Russia's ID in countries table
        self.country_code = "RU"

    def get_agency_id(self, agency_name_short: str) -> Optional[str]:
        """
        Get agency UUID from database by short name.

        Args:
            agency_name_short: Agency short name (e.g., "Минфин")

        Returns:
            Agency UUID or None if not found
        """
        with get_db_connection() as conn:
            result = conn.execute(
                text("""
                SELECT id FROM government_agencies
                WHERE country_id = :country_id AND agency_name_short = :agency_name
                """),
                {"country_id": self.country_id, "agency_name": agency_name_short}
            )
            row = result.fetchone()
            return row[0] if row else None

    def import_ministry_letter(self, letter: MinistryLetter) -> str:
        """
        Import a ministry letter into the database.

        Args:
            letter: MinistryLetter object

        Returns:
            UUID of inserted/updated letter record
        """
        # Get agency UUID
        agency_id = self.get_agency_id(letter.agency_name_short)
        if not agency_id:
            raise ValueError(f"Agency not found: {letter.agency_name_short}")

        related_laws_json = (
            json.dumps(letter.related_laws) if letter.related_laws else None
        )

        with get_db_connection() as conn:
            # Check if letter already exists
            existing = conn.execute(
                text("""
                SELECT id FROM official_interpretations
                WHERE country_id = :country_id AND agency_id = :agency_id
                  AND document_number = :doc_number AND document_date = :doc_date
                """),
                {
                    "country_id": self.country_id,
                    "agency_id": agency_id,
                    "doc_number": letter.document_number,
                    "doc_date": letter.document_date
                }
            ).fetchone()

            params = {
                "title": letter.title or "",
                "question": letter.question or "",
                "answer": letter.answer or "",
                "full_content": letter.full_content or "",
                "legal_topic": letter.legal_topic,
                "related_laws": related_laws_json,
                "binding_nature": letter.binding_nature,
                "source_url": letter.source_url,
            }

            if existing:
                # Update existing letter
                letter_uuid = existing[0]
                conn.execute(
                    text("""
                    UPDATE official_interpretations
                    SET title = :title, question = :question, answer = :answer,
                        full_content = :full_content, legal_topic = :legal_topic,
                        related_laws = :related_laws, binding_nature = :binding_nature,
                        source_url = :source_url, validity_status = 'valid',
                        updated_at = NOW()
                    WHERE id = :id
                    """),
                    {**params, "id": letter_uuid}
                )
                conn.commit()
                logger.debug(f"Updated ministry letter: {letter.document_number}")
            else:
                # Insert new letter
                result = conn.execute(
                    text("""
                    INSERT INTO official_interpretations
                    (country_id, country_code, agency_id, document_type,
                     document_number, document_date, title, question, answer,
                     full_content, legal_topic, related_laws, binding_nature,
                     validity_status, source_url)
                    VALUES (:country_id, :country_code, :agency_id, :document_type,
                            :document_number, :document_date, :title, :question, :answer,
                            :full_content, :legal_topic, :related_laws, :binding_nature,
                            'valid', :source_url)
                    RETURNING id
                    """),
                    {
                        **params,
                        "country_id": self.country_id,
                        "country_code": self.country_code,
                        "agency_id": agency_id,
                        "document_type": letter.document_type,
                        "document_number": letter.document_number,
                        "document_date": letter.document_date,
                    }
                )
                letter_uuid = result.fetchone()[0]
                conn.commit()
                logger.info(f"Inserted ministry letter: {letter.document_number}")

        return letter_uuid

    def import_agency_letters(
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
                self.import_ministry_letter(letter)
                stats["letters"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to import letter {letter.document_number}: {e}",
                    exc_info=True
                )
                stats["errors"] += 1

        return stats

    def import_all_phase7c_letters(
        self,
        years: int = 5,
        limit: Optional[int] = None
    ) -> Dict[str, Dict[str, int]]:
        """
        Import letters from all Phase 7C target agencies.

        Args:
            years: Number of years back to import (Phase 7C: 5 years)
            limit: Maximum number of letters to import per agency

        Returns:
            Dict mapping agency_key to import statistics
        """
        logger.info(f"Starting Phase 7C ministry letters import (last {years} years)")
        if limit:
            logger.info(f"Limit: {limit} letters per agency")

        # Fetch letters from all agencies
        all_letters = asyncio.run(fetch_all_phase7c_letters(years=years, limit=limit))

        # Import letters
        all_stats = {}
        for agency_key, letters in all_letters.items():
            try:
                stats = self.import_agency_letters(agency_key, letters)
                all_stats[agency_key] = stats
                logger.info(
                    f"Imported {stats['letters']} letters from {agency_key}"
                )
            except Exception as e:
                logger.error(f"Failed to import letters from {agency_key}: {e}", exc_info=True)
                all_stats[agency_key] = {"letters": 0, "errors": 1}

        # Log summary
        total_letters = sum(s["letters"] for s in all_stats.values())
        total_errors = sum(s["errors"] for s in all_stats.values())

        logger.info(
            f"Phase 7C ministry letters import complete: "
            f"{total_letters} letters, {total_errors} errors"
        )

        return all_stats

    def get_import_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on imported ministry letter data.

        Returns:
            Dict with import statistics
        """
        with get_db_connection() as conn:
            # Letters by agency
            letters_by_agency = conn.execute(
                text("""
                SELECT
                    ga.agency_name_short,
                    oi.document_type,
                    COUNT(*) as letter_count,
                    COUNT(*) FILTER (WHERE oi.validity_status = 'valid') as valid_count
                FROM official_interpretations oi
                JOIN government_agencies ga ON oi.agency_id = ga.id
                WHERE oi.country_id = :country_id
                GROUP BY ga.agency_name_short, oi.document_type
                ORDER BY ga.agency_name_short, oi.document_type
                """),
                {"country_id": self.country_id}
            ).fetchall()

            # Letters by topic
            letters_by_topic = conn.execute(
                text("""
                SELECT
                    legal_topic,
                    COUNT(*) as letter_count
                FROM official_interpretations
                WHERE country_id = :country_id AND legal_topic IS NOT NULL
                GROUP BY legal_topic
                ORDER BY letter_count DESC
                """),
                {"country_id": self.country_id}
            ).fetchall()

            # Total counts
            total_result = conn.execute(
                text("""
                SELECT
                    COUNT(*) as total_letters,
                    COUNT(*) FILTER (WHERE validity_status = 'valid') as valid_letters,
                    COUNT(DISTINCT agency_id) as agency_count
                FROM official_interpretations
                WHERE country_id = :country_id
                """),
                {"country_id": self.country_id}
            ).fetchone()

        return {
            "by_agency": letters_by_agency,
            "by_topic": letters_by_topic,
            "totals": {
                "total_letters": total_result[0] if total_result else 0,
                "valid_letters": total_result[1] if total_result else 0,
                "agency_count": total_result[2] if total_result else 0,
            },
        }


def main():
    """Main entry point for ministry letters import."""
    parser = argparse.ArgumentParser(description="Import ministry letters")
    parser.add_argument("--years", type=int, default=5, help="Number of years back to import")
    parser.add_argument("--limit", type=int, default=None, help="Maximum letters to import per agency")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting ministry letters import")
    if args.limit:
        logger.info(f"Test mode: limited to {args.limit} letters per agency")

    # Create importer
    importer = MinistryLetterImporter()

    # Import all Phase 7C letters
    stats = importer.import_all_phase7c_letters(years=args.years, limit=args.limit)

    # Get statistics
    statistics = importer.get_import_statistics()

    logger.info("Ministry letters import statistics:")
    logger.info(f"  Total letters: {statistics['totals'].get('total_letters', 0)}")
    logger.info(f"  Valid letters: {statistics['totals'].get('valid_letters', 0)}")
    logger.info(f"  Agencies: {statistics['totals'].get('agency_count', 0)}")


if __name__ == "__main__":
    main()
