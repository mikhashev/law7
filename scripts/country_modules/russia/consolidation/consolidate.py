"""
Consolidation Orchestrator for Russian Legal Codes.

This module orchestrates the consolidation process:
1. Fetch original code from pravo.gov.ru
2. Fetch all amendments chronologically
3. Apply amendments one by one
4. Store consolidated version with version history

Usage:
    python -m country_modules.russia.consolidation.consolidate --code TK_RF --rebuild

This is the Russia-specific consolidation orchestrator for Russian legal codes.
"""
import argparse
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from country_modules.russia.consolidation.amendment_parser import AmendmentParser, ParsedAmendment, parse_amendments_batch
from scripts.core.db import get_db_connection
from country_modules.russia.consolidation.diff_engine import ArticleDiffEngine, ArticleSnapshot
from country_modules.russia.consolidation.version_manager import VersionManager

logger = logging.getLogger(__name__)


# Country identification
country_id = "RUS"
country_name = "Russia"
country_code = "RU"


# Code metadata (original publication details)
CODE_METADATA = {
    'TK_RF': {
        'name': 'Трудовой кодекс',
        'eo_number': '197-ФЗ',
        'original_date': date(2001, 12, 30),
    },
    'GK_RF': {
        'name': 'Гражданский кодекс',
        'eo_number': '51-ФЗ',
        'original_date': date(1994, 11, 30),
    },
    'UK_RF': {
        'name': 'Уголовный кодекс',
        'eo_number': '63-ФЗ',
        'original_date': date(1996, 5, 24),
    },
    'NK_RF': {
        'name': 'Налоговый кодекс',
        'eo_number': '146-ФЗ',
        'original_date': date(2000, 7, 31),
    },
    # Add more codes as needed
}


class CodeConsolidator:
    """
    Orchestrates the consolidation of a legal code (Russia).

    This is the Russia-specific consolidator for Russian legal codes.

    Fetches the original code and all amendments, then applies them
    chronologically to produce the consolidated current version.

    Attributes:
        country_id: ISO 3166-1 alpha-3 code ("RUS")
        country_name: Full country name ("Russia")
        country_code: ISO 3166-1 alpha-2 code ("RU")
    """

    # Country identification
    country_id = "RUS"
    country_name = "Russia"
    country_code = "RU"

    def __init__(self, code_id: str):
        """
        Initialize the consolidator.

        Args:
            code_id: Code identifier (e.g., 'TK_RF', 'GK_RF')
        """
        if code_id not in CODE_METADATA:
            raise ValueError(f"Unknown code_id: {code_id}. Known codes: {list(CODE_METADATA.keys())}")

        self.code_id = code_id
        self.code_metadata = CODE_METADATA[code_id]

        self.parser = AmendmentParser()
        self.diff_engine = ArticleDiffEngine()
        self.version_manager = VersionManager()

        # Current state of articles
        self.current_articles: Dict[str, ArticleSnapshot] = {}

    def fetch_original_code(self) -> Dict[str, ArticleSnapshot]:
        """
        Fetch the original code publication.

        For now, this returns empty since we need to implement
        fetching from pravo.gov.ru or parsing from HTML.

        Returns:
            Dictionary of article_number -> ArticleSnapshot
        """
        # TODO: Implement fetching from pravo.gov.ru
        # For now, return empty dict
        logger.warning(f"Original code fetch not yet implemented for {self.code_id}")
        return {}

    def fetch_amendments(self, start_date: Optional[date] = None) -> List[ParsedAmendment]:
        """
        Fetch all amendments for this code from the database.

        Args:
            start_date: Optional start date for amendments

        Returns:
            List of parsed amendments, sorted by date
        """
        query = """
            SELECT
                d.eo_number,
                d.name as title,
                d.document_date,
                dc.full_text
            FROM documents d
            LEFT JOIN document_content dc ON d.id = dc.document_id
            WHERE dc.full_text IS NOT NULL
            AND dc.full_text LIKE :code_pattern
        """

        params = {'code_pattern': f'%{self.code_metadata["name"]}%'}

        if start_date:
            query += " AND d.document_date >= :start_date"
            params['start_date'] = start_date

        query += " ORDER BY d.document_date ASC"

        amendments = []

        try:
            with get_db_connection() as conn:
                result = conn.execute(text(query), params)

                for row in result:
                    parsed = self.parser.parse_amendment(
                        eo_number=row[0],
                        title=row[1],
                        text=row[3],
                        effective_date=row[2],
                    )

                    # Only include if it's actually for our code
                    if parsed.code_id == self.code_id:
                        amendments.append(parsed)

        except Exception as e:
            logger.error(f"Failed to fetch amendments: {e}")

        logger.info(f"Fetched {len(amendments)} amendments for {self.code_id}")
        return amendments

    def apply_amendment(
        self,
        current_articles: Dict[str, ArticleSnapshot],
        amendment: ParsedAmendment,
    ) -> Dict[str, ArticleSnapshot]:
        """
        Apply a single amendment to the current code state.

        Args:
            current_articles: Current state of articles
            amendment: Amendment to apply

        Returns:
            Updated articles dictionary
        """
        # For now, this is a simplified implementation
        # TODO: Implement proper amendment application logic

        logger.debug(f"Applying amendment {amendment.eo_number} to {self.code_id}")
        logger.debug(f"  Action type: {amendment.action_type}")
        logger.debug(f"  Articles affected: {len([c for c in amendment.changes if c.article_number])}")

        # Mark old versions as not current
        for change in amendment.changes:
            if change.article_number:
                self.version_manager.mark_old_versions_as_not_current(
                    self.code_id,
                    change.article_number,
                    amendment.effective_date or date.today(),
                )

        return current_articles

    def consolidate(
        self,
        rebuild: bool = False,
        start_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Run the full consolidation process.

        Args:
            rebuild: If True, rebuild from scratch (clear existing versions)
            start_date: Optional start date for amendments

        Returns:
            Dictionary with consolidation results
        """
        logger.info(f"Starting consolidation for {self.code_id}")
        logger.info(f"  Original: {self.code_metadata['eo_number']} from {self.code_metadata['original_date']}")

        # Step 1: Fetch original code
        logger.info("[Step 1] Fetching original code...")
        self.current_articles = self.fetch_original_code()

        # Step 2: Fetch all amendments
        logger.info("[Step 2] Fetching amendments...")
        amendments = self.fetch_amendments(start_date)

        if not amendments:
            logger.warning("No amendments found, nothing to consolidate")
            return {
                'code_id': self.code_id,
                'status': 'completed',
                'amendments_processed': 0,
                'articles_updated': 0,
            }

        # Step 3: Apply amendments chronologically
        logger.info(f"[Step 3] Applying {len(amendments)} amendments...")
        articles_updated = 0

        for i, amendment in enumerate(amendments):
            logger.debug(f"  [{i+1}/{len(amendments)}] Processing {amendment.eo_number}...")

            try:
                # Parse detailed changes from amendment text
                changes = self.parser.parse_change_details(amendment, amendment.raw_text)
                amendment.changes = changes

                # Apply the amendment
                self.current_articles = self.apply_amendment(
                    self.current_articles,
                    amendment,
                )

                articles_updated += len([c for c in changes if c.article_number])

            except Exception as e:
                logger.error(f"  Failed to apply amendment {amendment.eo_number}: {e}")
                continue

        # Step 4: Save results
        logger.info("[Step 4] Saving consolidated versions...")

        # For each article, save the final snapshot
        snapshots_saved = 0
        for article_number, article in self.current_articles.items():
            if self.version_manager.save_snapshot(self.code_id, article):
                snapshots_saved += 1

        logger.info(f"  Saved {snapshots_saved} article snapshots")

        results = {
            'code_id': self.code_id,
            'status': 'completed',
            'amendments_processed': len(amendments),
            'articles_updated': articles_updated,
            'snapshots_saved': snapshots_saved,
        }

        logger.info(f"Consolidation complete: {results}")
        return results


def consolidate_code(
    code_id: str,
    rebuild: bool = False,
    start_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Convenience function to consolidate a code.

    Args:
        code_id: Code identifier (e.g., 'TK_RF', 'GK_RF')
        rebuild: If True, rebuild from scratch
        start_date: Optional start date for amendments

    Returns:
        Dictionary with consolidation results

    Example:
        >>> from country_modules.russia.consolidation.consolidate import consolidate_code
        >>> results = consolidate_code('TK_RF')
        >>> print(f"Processed {results['amendments_processed']} amendments")
    """
    consolidator = CodeConsolidator(code_id)
    return consolidator.consolidate(rebuild=rebuild, start_date=start_date)


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(description="Consolidate Russian legal codes")
    parser.add_argument(
        '--code',
        required=True,
        choices=list(CODE_METADATA.keys()),
        help='Code identifier to consolidate',
    )
    parser.add_argument(
        '--rebuild',
        action='store_true',
        help='Rebuild from scratch (clear existing versions)',
    )
    parser.add_argument(
        '--start-date',
        help='Start date for amendments (YYYY-MM-DD)',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging',
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # Parse start date
    start_date = None
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()

    # Run consolidation
    results = consolidate_code(
        code_id=args.code,
        rebuild=args.rebuild,
        start_date=start_date,
    )

    # Print results
    print("\n" + "="*60)
    print("Consolidation Results")
    print("="*60)
    print(f"Code: {results['code_id']}")
    print(f"Status: {results['status']}")
    print(f"Amendments processed: {results['amendments_processed']}")
    print(f"Articles updated: {results['articles_updated']}")
    print(f"Snapshots saved: {results['snapshots_saved']}")
    print("="*60)


if __name__ == "__main__":
    main()
