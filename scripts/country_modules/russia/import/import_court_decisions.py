"""
Import court decisions for Phase 7C (Supreme Court + Constitutional Court).

This script imports court decision data into the database following the
country_modules architecture established in Phase 7A/7B.

Phase 7C scope:
- Supreme Court: Plenary resolutions, practice reviews
- Constitutional Court: Rulings, determinations with legal positions
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
from country_modules.russia.scrapers.court_scraper import (
    CourtScraper,
    CourtDecision,
    PracticeReview,
    LegalPosition,
)

logger = logging.getLogger(__name__)


class CourtDecisionImporter:
    """
    Import court decision data into the database.
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

    async def import_court_decision(self, decision: CourtDecision) -> str:
        """
        Import a court decision into the database.

        Args:
            decision: CourtDecision object

        Returns:
            UUID of inserted/updated decision record
        """
        # Check if decision already exists (by case_number and decision_date)
        existing = await self.db.execute(
            """
            SELECT id FROM court_decisions
            WHERE country_id = $1 AND court_type = $2
              AND case_number = $3 AND decision_date = $4
            """,
            self.country_id,
            decision.court_type,
            decision.case_number,
            decision.decision_date
        )

        articles_interpreted_json = (
            json.dumps(decision.articles_interpreted)
            if decision.articles_interpreted
            else None
        )

        if existing:
            # Update existing decision
            decision_uuid = existing[0]["id"]
            await self.db.execute(
                """
                UPDATE court_decisions
                SET title = $1, summary = $2, full_text = $3,
                    legal_issues = $4, articles_interpreted = $5,
                    binding_nature = $6, source_url = $7,
                    status = 'active', updated_at = NOW()
                WHERE id = $8
                """,
                decision.title,
                decision.summary,
                decision.full_text,
                decision.legal_issues or [],
                articles_interpreted_json,
                decision.binding_nature,
                decision.source_url,
                decision_uuid
            )
            logger.debug(f"Updated court decision: {decision.case_number}")
        else:
            # Insert new decision
            result = await self.db.execute(
                """
                INSERT INTO court_decisions
                (country_id, country_code, court_type, court_level, decision_type,
                 case_number, decision_date, title, summary, full_text,
                 legal_issues, articles_interpreted, binding_nature, status, source_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
                """,
                self.country_id,
                self.country_code,
                decision.court_type,
                "federal",  # Supreme and Constitutional are federal courts
                decision.decision_type,
                decision.case_number,
                decision.decision_date,
                decision.title,
                decision.summary,
                decision.full_text,
                decision.legal_issues or [],
                articles_interpreted_json,
                decision.binding_nature,
                "active",
                decision.source_url
            )
            decision_uuid = result[0]["id"]
            logger.info(f"Inserted court decision: {decision.case_number}")

        return decision_uuid

    async def import_practice_review(self, review: PracticeReview) -> str:
        """
        Import a practice review into the database.

        Args:
            review: PracticeReview object

        Returns:
            UUID of inserted/updated review record
        """
        # Check if review already exists
        existing = await self.db.execute(
            """
            SELECT id FROM practice_reviews
            WHERE country_id = $1 AND court_type = $2
              AND review_title = $3 AND publication_date = $4
            """,
            self.country_id,
            review.court_type,
            review.review_title,
            review.publication_date
        )

        if existing:
            # Update existing review
            review_uuid = existing[0]["id"]
            await self.db.execute(
                """
                UPDATE practice_reviews
                SET period_covered = $1, content = $2,
                    key_conclusions = $3, common_errors = $4,
                    correct_approach = $5, cases_analyzed = $6,
                    source_url = $7, updated_at = NOW()
                WHERE id = $8
                """,
                review.period_covered,
                review.content,
                review.key_conclusions or [],
                review.common_errors or [],
                review.correct_approaches or [],
                review.cases_analyzed,
                review.source_url,
                review_uuid
            )
            logger.debug(f"Updated practice review: {review.review_title}")
        else:
            # Insert new review
            result = await self.db.execute(
                """
                INSERT INTO practice_reviews
                (country_id, country_code, court_type, review_title, publication_date,
                 period_covered, content, key_conclusions, common_errors,
                 correct_approach, cases_analyzed, source_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
                """,
                self.country_id,
                self.country_code,
                review.court_type,
                review.review_title,
                review.publication_date,
                review.period_covered,
                review.content,
                review.key_conclusions or [],
                review.common_errors or [],
                review.correct_approaches or [],
                review.cases_analyzed,
                review.source_url
            )
            review_uuid = result[0]["id"]
            logger.info(f"Inserted practice review: {review.review_title}")

        return review_uuid

    async def import_legal_position(
        self,
        decision_id: str,
        position: LegalPosition
    ) -> str:
        """
        Import a legal position from Constitutional Court.

        Args:
            decision_id: UUID of the related court decision
            position: LegalPosition object

        Returns:
            UUID of inserted position record
        """
        # Check if position already exists
        existing = await self.db.execute(
            """
            SELECT id FROM legal_positions
            WHERE decision_id = $1 AND position_text = $2
            """,
            decision_id,
            position.position_text
        )

        if existing:
            # Update existing position
            position_uuid = existing[0]["id"]
            await self.db.execute(
                """
                UPDATE legal_positions
                SET constitutional_basis = $1, laws_affected = $2,
                    position_date = $3, still_valid = $4
                WHERE id = $5
                """,
                position.constitutional_basis or [],
                position.laws_affected or [],
                position.position_date,
                position.still_valid,
                position_uuid
            )
            logger.debug(f"Updated legal position for decision {decision_id}")
        else:
            # Insert new position
            result = await self.db.execute(
                """
                INSERT INTO legal_positions
                (country_id, country_code, decision_id, position_text,
                 constitutional_basis, laws_affected, position_date, still_valid)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                self.country_id,
                self.country_code,
                decision_id,
                position.position_text,
                position.constitutional_basis or [],
                position.laws_affected or [],
                position.position_date,
                position.still_valid
            )
            position_uuid = result[0]["id"]
            logger.info(f"Inserted legal position for decision {decision_id}")

        return position_uuid

    async def import_supreme_court_data(
        self,
        decisions: List[CourtDecision],
        reviews: List[PracticeReview]
    ) -> Dict[str, int]:
        """
        Import Supreme Court data.

        Args:
            decisions: List of Supreme Court decisions
            reviews: List of practice reviews

        Returns:
            Dict with import statistics
        """
        stats = {
            "decisions": 0,
            "reviews": 0,
            "errors": 0
        }

        # Import decisions
        for decision in decisions:
            try:
                await self.import_court_decision(decision)
                stats["decisions"] += 1
            except Exception as e:
                logger.error(f"Failed to import decision {decision.case_number}: {e}")
                stats["errors"] += 1

        # Import practice reviews
        for review in reviews:
            try:
                await self.import_practice_review(review)
                stats["reviews"] += 1
            except Exception as e:
                logger.error(f"Failed to import review {review.review_title}: {e}")
                stats["errors"] += 1

        return stats

    async def import_constitutional_court_data(
        self,
        decisions: List[CourtDecision],
        positions: Optional[List[LegalPosition]] = None
    ) -> Dict[str, int]:
        """
        Import Constitutional Court data.

        Args:
            decisions: List of Constitutional Court rulings
            positions: List of legal positions

        Returns:
            Dict with import statistics
        """
        stats = {
            "decisions": 0,
            "positions": 0,
            "errors": 0
        }

        # Import decisions
        decision_map = {}  # Map case_number to decision UUID
        for decision in decisions:
            try:
                decision_uuid = await self.import_court_decision(decision)
                decision_map[decision.case_number] = decision_uuid
                stats["decisions"] += 1
            except Exception as e:
                logger.error(f"Failed to import decision {decision.case_number}: {e}")
                stats["errors"] += 1

        # Import legal positions
        if positions:
            for position in positions:
                try:
                    decision_uuid = decision_map.get(position.decision_id)
                    if decision_uuid:
                        await self.import_legal_position(decision_uuid, position)
                        stats["positions"] += 1
                    else:
                        logger.warning(f"No decision found for position: {position.decision_id}")
                except Exception as e:
                    logger.error(f"Failed to import legal position: {e}")
                    stats["errors"] += 1

        return stats

    async def import_all_phase7c_court_data(self) -> Dict[str, Dict[str, int]]:
        """
        Import all Phase 7C court data.

        Returns:
            Dict mapping court type to import statistics
        """
        logger.info("Starting Phase 7C court decision import")

        all_stats = {}

        # Import Supreme Court data
        try:
            supreme_scraper = CourtScraper("supreme")
            supreme_data = await supreme_scraper.fetch_all_phase7c_court_data()
            supreme_stats = await self.import_supreme_court_data(
                supreme_data["supreme_court"]["plenary_resolutions"],
                supreme_data["supreme_court"]["practice_reviews"]
            )
            all_stats["supreme_court"] = supreme_stats
        except Exception as e:
            logger.error(f"Failed to import Supreme Court data: {e}")
            all_stats["supreme_court"] = {"decisions": 0, "reviews": 0, "errors": 1}

        # Import Constitutional Court data
        try:
            constitutional_stats = await self.import_constitutional_court_data(
                [],  # TODO: fetch actual rulings
                []   # TODO: fetch actual positions
            )
            all_stats["constitutional_court"] = constitutional_stats
        except Exception as e:
            logger.error(f"Failed to import Constitutional Court data: {e}")
            all_stats["constitutional_court"] = {"decisions": 0, "positions": 0, "errors": 1}

        # Log summary
        total_decisions = sum(
            s.get("decisions", 0) for s in all_stats.values()
        )
        total_reviews = all_stats.get("supreme_court", {}).get("reviews", 0)
        total_positions = all_stats.get("constitutional_court", {}).get("positions", 0)
        total_errors = sum(
            s.get("errors", 0) for s in all_stats.values()
        )

        logger.info(
            f"Phase 7C court import complete: "
            f"{total_decisions} decisions, {total_reviews} reviews, "
            f"{total_positions} positions, {total_errors} errors"
        )

        return all_stats

    async def get_import_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on imported court data.

        Returns:
            Dict with import statistics
        """
        # Court decisions
        decisions = await self.db.execute(
            """
            SELECT court_type, decision_type,
                   COUNT(*) as decision_count,
                   COUNT(*) FILTER (WHERE status = 'active') as active_count
            FROM court_decisions
            WHERE country_id = $1
            GROUP BY court_type, decision_type
            ORDER BY court_type, decision_type
            """,
            self.country_id
        )

        # Practice reviews
        reviews = await self.db.execute(
            """
            SELECT court_type, COUNT(*) as review_count
            FROM practice_reviews
            WHERE country_id = $1
            GROUP BY court_type
            """,
            self.country_id
        )

        # Legal positions
        positions = await self.db.execute(
            """
            SELECT COUNT(*) as position_count,
                   COUNT(*) FILTER (WHERE still_valid = true) as valid_count
            FROM legal_positions
            WHERE country_id = $1
            """,
            self.country_id
        )

        return {
            "decisions": decisions,
            "reviews": reviews,
            "positions": positions[0] if positions else {},
            "total_decisions": sum(row["decision_count"] for row in decisions),
            "total_reviews": sum(row["review_count"] for row in reviews),
        }


async def main():
    """Main entry point for court decision import."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting court decision import")

    # Initialize database
    settings = get_settings()
    db = DatabaseClient(settings)
    await db.connect()

    try:
        # Create importer
        importer = CourtDecisionImporter(db)

        # Import all Phase 7C court data
        stats = await importer.import_all_phase7c_court_data()

        # Get statistics
        statistics = await importer.get_import_statistics()

        logger.info("Court decision import statistics:")
        logger.info(f"  Total decisions: {statistics['total_decisions']}")
        logger.info(f"  Total reviews: {statistics['total_reviews']}")
        logger.info(f"  Total positions: {statistics['positions'].get('position_count', 0)}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
