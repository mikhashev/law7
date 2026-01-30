"""
Scrape Article Number Structure from Consultant.ru

This script scrapes the standardized article number structure from consultant.ru
for comparison and verification of articles imported from official sources.

Usage:
    python -m scripts.import.scrape_consultant_structure --code KoAP_RF
    python -m scripts.import.scrape_consultant_structure --list

The consultant.ru document IDs for supported codes:
- KoAP_RF: cons_doc_LAW_34661
"""

import argparse
import logging
import re
import sys
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# HTTP request settings
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1


# Consultant.ru document IDs for supported codes
CONSULTANT_DOC_IDS = {
    'KONST_RF': 'cons_doc_LAW_30994',  # Constitution
    'GK_RF': 'cons_doc_LAW_30712',     # Civil Code Part 1
    'GK_RF_2': 'cons_doc_LAW_30713',    # Civil Code Part 2
    'GK_RF_3': 'cons_doc_LAW_30714',    # Civil Code Part 3
    'GK_RF_4': 'cons_doc_LAW_30715',    # Civil Code Part 4
    'UK_RF': 'cons_doc_LAW_30645',      # Criminal Code
    'TK_RF': 'cons_doc_LAW_30648',      # Labor Code
    'NK_RF': 'cons_doc_LAW_30735',      # Tax Code Part 1
    'NK_RF_2': 'cons_doc_LAW_30736',     # Tax Code Part 2
    'KoAP_RF': 'cons_doc_LAW_34661',    # Administrative Code
    'SK_RF': 'cons_doc_LAW_30656',      # Family Code
    'ZhK_RF': 'cons_doc_LAW_31120',     # Housing Code
    'ZK_RF': 'cons_doc_LAW_30739',      # Land Code
    'APK_RF': 'cons_doc_LAW_30644',     # Arbitration Procedure Code
    'GPK_RF': 'cons_doc_LAW_30642',     # Civil Procedure Code
    'UPK_RF': 'cons_doc_LAW_30643',     # Criminal Procedure Code
    'BK_RF': 'cons_doc_LAW_30570',      # Budget Code
    'GRK_RF': 'cons_doc_LAW_30725',     # Urban Planning Code
    'UIK_RF': 'cons_doc_LAW_30577',     # Criminal Executive Code
    'VZK_RF': 'cons_doc_LAW_30646',     # Air Code
    'VDK_RF': 'cons_doc_LAW_30641',     # Water Code
    'LK_RF': 'cons_doc_LAW_30756',      # Forest Code
    'KAS_RF': 'cons_doc_LAW_30648',     # Administrative Procedure Code
}


def scrape_article_numbers_from_consultant(doc_id: str) -> List[str]:
    """
    Scrape all article numbers from a consultant.ru document page.

    Args:
        doc_id: Consultant.ru document ID (e.g., 'cons_doc_LAW_34661')

    Returns:
        List of article numbers found in the document
    """
    url = f"https://www.consultant.ru/document/{doc_id}/"
    article_numbers = []

    try:
        logger.info(f"Fetching article structure from {url}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all article links in the document
        # Consultant.ru uses pattern: /document/DOCID/hash/
        # We look for links that contain article numbers
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Match article pattern: e.g., "Статья 1.3.1" or just "1.3.1"
            match = re.search(r'(?:Статья\s+)?(\d+(?:\.\d+)*)(?:\.|$)', link.get_text())
            if match:
                article_num = match.group(1)
                if article_num not in article_numbers:
                    article_numbers.append(article_num)

        # Alternative: scrape from document text
        # Look for patterns like "Статья 1.3.1." in the page
        pattern = r'Статья\s+(\d+(?:\.\d+)*)(?:\.|\s|$)'
        for match in re.finditer(pattern, response.text):
            article_num = match.group(1)
            if article_num not in article_numbers:
                article_numbers.append(article_num)

        article_numbers.sort(key=lambda x: [int(p) for p in x.split('.')])
        logger.info(f"Found {len(article_numbers)} articles in consultant.ru structure")

    except Exception as e:
        logger.error(f"Failed to scrape article numbers from {url}: {e}")

    return article_numbers


def import_reference_to_database(code_id: str, article_numbers: List[str]) -> int:
    """
    Import consultant.ru article number reference to database.

    Creates mappings from our format (kremlin.ru) to consultant.ru format by matching
    article titles.

    Args:
        code_id: Code identifier
        article_numbers: List of article numbers from consultant.ru

    Returns:
        Number of reference mappings created
    """
    from scripts.core.db import get_db_connection
    from sqlalchemy import text

    imported = 0

    try:
        with get_db_connection() as conn:
            # Ensure reference table exists
            create_table_query = text(
                """
                CREATE TABLE IF NOT EXISTS article_number_reference (
                    id SERIAL PRIMARY KEY,
                    code_id VARCHAR(50) NOT NULL,
                    article_number_source VARCHAR(50) NOT NULL,
                    article_number_consultant VARCHAR(50) NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    verification_notes TEXT,
                    created_at TIMESTAMP DEFAULT now(),
                    UNIQUE(code_id, article_number_source, article_number_consultant)
                );

                CREATE INDEX IF NOT EXISTS idx_article_number_reference_code_id
                ON article_number_reference(code_id);

                CREATE INDEX IF NOT EXISTS idx_article_number_reference_consultant
                ON article_number_reference(code_id, article_number_consultant);
                """
            )
            conn.execute(create_table_query)

            # Get existing articles with titles for matching
            our_articles_query = text(
                """
                SELECT article_number, article_title, text_hash
                FROM code_article_versions
                WHERE code_id = :code_id
                """
            )
            result = conn.execute(our_articles_query, {"code_id": code_id})
            our_articles = {row[0]: (row[1], row[2]) for row in result}
            logger.info(f"Found {len(our_articles)} existing articles for {code_id}")

            # Fetch article titles from consultant.ru for each consultant article number
            # This creates mappings: our format ("1.31") -> consultant format ("1.3.1")
            params_list = []

            for consultant_article in article_numbers:
                # Skip section numbers (single digit without dot)
                if '.' not in consultant_article and len(consultant_article) <= 2:
                    continue

                # Try to find matching article by similar number pattern
                # "1.3.1" -> look for "1.31" (remove middle dot, keep last digit)
                # "1.3" -> look for "1.3" (exact match)
                # "10.5.1" -> look for "105.1" (remove first dot)

                possible_source_formats = []
                if consultant_article.count('.') >= 2:
                    # "1.3.1" -> "1.31"
                    parts = consultant_article.split('.')
                    if len(parts) == 3 and len(parts[1]) == 1:
                        possible_source_formats.append(f"{parts[0]}.{parts[1]}{parts[2]}")
                elif consultant_article.count('.') == 1:
                    # "10.5" -> could be "105" or "10.5"
                    possible_source_formats.append(consultant_article)

                # Find matching article by checking if our format exists
                for source_format in possible_source_formats:
                    if source_format in our_articles:
                        title, text_hash = our_articles[source_format]
                        params = {
                            "code_id": code_id,
                            "article_number_source": source_format,
                            "article_number_consultant": consultant_article,
                            "is_verified": True,
                            "verification_notes": f"Auto-matched: {source_format} -> {consultant_article}",
                        }
                        params_list.append(params)
                        logger.debug(f"Matched: {source_format} -> {consultant_article}")
                        break
                else:
                    # Article exists in consultant.ru but not in our database
                    logger.debug(f"Consultant article {consultant_article} not found in our database")

            if params_list:
                insert_query = text(
                    """
                    INSERT INTO article_number_reference (
                        code_id, article_number_source, article_number_consultant,
                        is_verified, verification_notes
                    ) VALUES (
                        :code_id, :article_number_source, :article_number_consultant,
                        :is_verified, :verification_notes
                    )
                    ON CONFLICT (code_id, article_number_source, article_number_consultant)
                    DO UPDATE SET
                        is_verified = EXCLUDED.is_verified,
                        verification_notes = EXCLUDED.verification_notes
                    """
                )
                conn.execute(insert_query, params_list)
                imported = len(params_list)
                conn.commit()

            logger.info(f"Imported {imported} reference mappings for {code_id}")

    except Exception as e:
        logger.error(f"Failed to import reference for {code_id}: {e}")

    return imported


def verify_article_numbers(code_id: str) -> Dict[str, any]:
    """
    Verify imported article numbers against consultant.ru reference.

    Reports:
    - Articles in database but not in consultant.ru reference
    - Articles in consultant.ru but not in database
    - Format mismatches (same content, different number)

    Args:
        code_id: Code identifier to verify

    Returns:
        Dictionary with verification results
    """
    from scripts.core.db import get_db_connection
    from sqlalchemy import text

    try:
        with get_db_connection() as conn:
            # Get consultant.ru reference
            ref_query = text(
                """
                SELECT article_number_consultant
                FROM article_number_reference
                WHERE code_id = :code_id
                ORDER BY article_number_consultant
                """
            )
            result = conn.execute(ref_query, {"code_id": code_id})
            consultant_articles = set(row[0] for row in result)

            # Get imported articles
            imp_query = text(
                """
                SELECT article_number
                FROM code_article_versions
                WHERE code_id = :code_id
                ORDER BY article_number
                """
            )
            result = conn.execute(imp_query, {"code_id": code_id})
            imported_articles = set(row[0] for row in result)

            # Find differences
            in_db_not_ref = imported_articles - consultant_articles
            in_ref_not_db = consultant_articles - imported_articles

            return {
                "code_id": code_id,
                "total_in_db": len(imported_articles),
                "total_in_consultant": len(consultant_articles),
                "in_db_not_in_reference": sorted(list(in_db_not_ref)),
                "in_reference_not_in_db": sorted(list(in_ref_not_db)),
                "common_count": len(imported_articles & consultant_articles),
            }

    except Exception as e:
        logger.error(f"Failed to verify articles for {code_id}: {e}")
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Scrape article number structure from consultant.ru"
    )
    parser.add_argument(
        '--code',
        type=str,
        help='Code identifier to scrape (e.g., KoAP_RF)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all supported codes'
    )
    parser.add_argument(
        '--verify',
        type=str,
        metavar='CODE_ID',
        help='Verify articles against consultant.ru reference'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Import reference for all supported codes'
    )

    args = parser.parse_args()

    if args.list:
        print("Supported codes for consultant.ru structure scraping:")
        for code_id in sorted(CONSULTANT_DOC_IDS.keys()):
            print(f"  {code_id}")
        return 0

    if args.verify:
        results = verify_article_numbers(args.verify)
        print(f"\nVerification results for {args.verify}:")
        print(f"  Total in database: {results.get('total_in_db', 0)}")
        print(f"  Total in consultant.ru: {results.get('total_in_consultant', 0)}")
        print(f"  Common: {results.get('common_count', 0)}")

        if results.get('in_db_not_in_reference'):
            print(f"\n  In DB but not in consultant.ru ({len(results['in_db_not_in_reference'])}):")
            for art in results['in_db_not_in_reference'][:10]:
                print(f"    {art}")
            if len(results['in_db_not_in_reference']) > 10:
                print(f"    ... and {len(results['in_db_not_in_reference']) - 10} more")

        if results.get('in_reference_not_in_db'):
            print(f"\n  In consultant.ru but not in DB ({len(results['in_reference_not_in_db'])}):")
            for art in results['in_reference_not_in_db'][:10]:
                print(f"    {art}")
            if len(results['in_reference_not_in_db']) > 10:
                print(f"    ... and {len(results['in_reference_not_in_db']) - 10} more")
        return 0

    if args.all:
        print("Importing consultant.ru structure for all codes...")
        for code_id in CONSULTANT_DOC_IDS:
            doc_id = CONSULTANT_DOC_IDS[code_id]
            logger.info(f"Processing {code_id} (doc_id: {doc_id})")
            articles = scrape_article_numbers_from_consultant(doc_id)
            if articles:
                count = import_reference_to_database(code_id, articles)
                print(f"  {code_id}: {count} articles imported")
        return 0

    if args.code:
        if args.code not in CONSULTANT_DOC_IDS:
            print(f"Error: Code '{args.code}' not found in consultant.ru mapping")
            print("Use --list to see supported codes")
            return 1

        doc_id = CONSULTANT_DOC_IDS[args.code]
        logger.info(f"Processing {args.code} (doc_id: {doc_id})")
        articles = scrape_article_numbers_from_consultant(doc_id)

        if articles:
            print(f"\nFound {len(articles)} articles from consultant.ru:")
            print("Sample articles (first 20):")
            for art in articles[:20]:
                print(f"  {art}")
            if len(articles) > 20:
                print(f"  ... and {len(articles) - 20} more")

            count = import_reference_to_database(args.code, articles)
            print(f"\nImported {count} reference mappings to database")
        else:
            print(f"No articles found for {args.code}")
            return 1

        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
