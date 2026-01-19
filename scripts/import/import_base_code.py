"""
Import Base Legal Codes from Official Sources

This script imports the original/base text of Russian legal codes from:
1. pravo.gov.ru (official publication portal)
2. consultant.ru (free reference copy)

The imported base code text serves as the foundation for applying amendments
during the consolidation process.

Usage:
    python -m scripts.import.import_base_code --code TK_RF --source consultant
    python -m scripts.import.import_base_code --code GK_RF --source pravo
    python -m scripts.import.import_base_code --list
"""
import argparse
import logging
import re
import sys
import time
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

from scripts.core.db import get_db_connection

logger = logging.getLogger(__name__)


# Code metadata for import
# Priority: kremlin (official) -> pravo (official) -> consultant (reference)
CODE_METADATA = {
    'TK_RF': {
        'name': 'Трудовой кодекс',
        'eo_number': '197-ФЗ',
        'original_date': date(2001, 12, 30),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_34683/',
        'kremlin_bank': '17706',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/17706',
    },
    'GK_RF': {
        'name': 'Гражданский кодекс',
        'eo_number': '51-ФЗ',
        'original_date': date(1994, 11, 30),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_5142/',
        'kremlin_bank': '7279',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/7279',
    },
    'UK_RF': {
        'name': 'Уголовный кодекс',
        'eo_number': '63-ФЗ',
        'original_date': date(1996, 5, 24),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_10699/',
        'kremlin_bank': '9555',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/9555',
    },
    'NK_RF': {
        'name': 'Налоговый кодекс',
        'eo_number': '146-ФЗ',
        'original_date': date(2000, 7, 31),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_19671/',
        'kremlin_bank': '12755',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/12755',
    },
    'KoAP_RF': {
        'name': 'Кодекс Российской Федерации об административных правонарушениях',
        'eo_number': '195-ФЗ',
        'original_date': date(2001, 12, 30),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_19702/',
        'kremlin_bank': '17704',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/17704',
    },
    'SK_RF': {
        'name': 'Семейный кодекс',
        'eo_number': '223-ФЗ',
        'original_date': date(1995, 12, 29),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_12940/',
        'kremlin_bank': '8671',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/8671',
    },
    'ZhK_RF': {
        'name': 'Жилищный кодекс',
        'eo_number': '188-ФЗ',
        'original_date': date(2004, 12, 29),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_51057/',
        'kremlin_bank': '21918',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/21918',
    },
    'ZK_RF': {
        'name': 'Земельный кодекс',
        'eo_number': '136-ФЗ',
        'original_date': date(2001, 10, 25),
        'consultant_url': 'https://www.consultant.ru/document/cons_doc_LAW_33773/',
        'kremlin_bank': '17478',
        'kremlin_url': 'http://www.kremlin.ru/acts/bank/17478',
    },
}


class BaseCodeImporter:
    """
    Import base legal code text from online sources.

    Supports:
    - consultant.ru: Free reference copy with HTML structure
    - pravo.gov.ru: Official publication (when available)
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize the importer.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

    def fetch_consultant_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML from consultant.ru.

        Args:
            url: Full URL to the code page

        Returns:
            HTML content or None if failed
        """
        try:
            logger.info(f"Fetching from: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch from consultant.ru: {e}")
            return None

    def parse_consultant_html(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse consultant.ru HTML to extract article links.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        soup = BeautifulSoup(html, 'html.parser')

        articles = []
        base_url = CODE_METADATA[code_id]['consultant_url']

        # Find all article links in the table of contents
        # Consultant.ru uses a navigation structure with article links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Match article links like "Статья 1. Title" or "#doc-..."
            article_match = re.search(r'Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)?', text, re.IGNORECASE)

            if article_match:
                article_number = article_match.group(1).replace('.', '').replace('-', '')
                article_title = text

                # Build full URL for article page
                article_url = urljoin(base_url, href)

                articles.append({
                    'article_number': article_number,
                    'article_title': article_title,
                    'article_url': article_url,
                    'article_text': '',  # Will fetch separately
                })

        logger.info(f"Found {len(articles)} article links from consultant.ru table of contents")
        return {
            'code_id': code_id,
            'articles': articles,
            'source': 'consultant.ru',
        }

    def fetch_article_text(self, article_url: str, article_number: str) -> str:
        """
        Fetch full text for a single article from its page.

        Args:
            article_url: URL to article page
            article_number: Article number

        Returns:
            Article text content
        """
        try:
            logger.debug(f"Fetching article {article_number} from {article_url}")
            response = self.session.get(article_url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove unwanted elements
            for element in soup(['script', 'style', 'noscript', 'nav', 'footer', 'header']):
                element.decompose()

            # Find main content - consultant.ru typically uses specific containers
            main_content = (
                soup.find('div', class_='document-text') or
                soup.find('div', class_='docitem') or
                soup.find('article') or
                soup.find('main')
            )

            if main_content:
                # Extract text while preserving paragraphs
                paragraphs = []
                for p in main_content.find_all(['p', 'div', 'section']):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:  # Filter out very short elements
                        paragraphs.append(text)

                article_text = '\n\n'.join(paragraphs)
            else:
                # Fallback: get all text
                article_text = soup.get_text(separator='\n', strip=True)

            return article_text[:50000]  # Limit text length

        except Exception as e:
            logger.error(f"Failed to fetch article {article_number}: {e}")
            return ''

    def fetch_kremlin_html(self, bank_id: str) -> Optional[str]:
        """
        Fetch HTML from kremlin.ru (official publication portal).

        Args:
            bank_id: Kremlin bank ID (e.g., '7279' for Civil Code)

        Returns:
            HTML content or None if failed
        """
        url = f"http://www.kremlin.ru/acts/bank/{bank_id}/page/1"
        try:
            logger.info(f"Fetching from Kremlin: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch from kremlin.ru: {e}")
            return None

    def fetch_kremlin_html_all_pages(self, bank_id: str) -> List[str]:
        """
        Fetch ALL HTML pages from kremlin.ru (official publication portal).

        Args:
            bank_id: Kremlin bank ID (e.g., '7279' for Civil Code)

        Returns:
            List of HTML content strings (one per page), or empty list if failed
        """
        all_pages = []
        page_num = 1

        while True:
            url = f"http://www.kremlin.ru/acts/bank/{bank_id}/page/{page_num}"
            try:
                logger.info(f"Fetching page {page_num}: {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = 'utf-8'

                # Check if this page has articles (look for article patterns in text)
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text()
                has_articles = bool(re.search(r'Статья\s+\d+', text))

                if not has_articles:
                    logger.info(f"Page {page_num} has no articles, stopping pagination")
                    break

                all_pages.append(response.text)
                page_num += 1

                # Sleep to avoid rate limiting
                time.sleep(1)

                # Safety limit to prevent infinite loops
                if page_num > 100:
                    logger.warning(f"Reached page limit (100), stopping pagination")
                    break

            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                # If we got some pages, return them. If first page failed, return empty
                if page_num > 1:
                    break
                return []

        logger.info(f"Fetched {len(all_pages)} pages from kremlin.ru")
        return all_pages

    def parse_kremlin_html(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse kremlin.ru HTML to extract articles.

        The Kremlin source has full article text directly on the page, with
        articles marked by headers like "Статья 1. Title" and numbered paragraphs.

        Args:
            html: HTML content (single page string or list of pages)
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        # Handle multiple pages
        if isinstance(html, list):
            all_articles = []
            for i, page_html in enumerate(html):
                result = self._parse_single_kremlin_page(page_html, code_id)
                all_articles.extend(result.get('articles', []))
            logger.info(f"Parsed {len(all_articles)} articles from {len(html)} pages")
            return {
                'code_id': code_id,
                'articles': all_articles,
                'source': 'kremlin.ru',
            }
        else:
            return self._parse_single_kremlin_page(html, code_id)

    def _parse_single_kremlin_page(self, html: str, code_id: str) -> Dict[str, Any]:
        """
        Parse a single kremlin.ru HTML page to extract articles.

        Args:
            html: HTML content
            code_id: Code identifier

        Returns:
            Dictionary with articles list
        """
        soup = BeautifulSoup(html, 'html.parser')

        articles = []
        current_article = None
        current_paragraphs = []

        # Find all text elements
        for element in soup.find_all(['h4', 'p', 'div']):
            text = element.get_text(strip=True)

            # Check if this is an article header
            article_match = re.match(r'^Статья\s+(\d+(?:[\.\-]\d+)*)\.?\s*(.+)$', text, re.IGNORECASE)

            if article_match:
                # Save previous article if exists
                if current_article and current_paragraphs:
                    current_article['article_text'] = '\n\n'.join(current_paragraphs)
                    articles.append(current_article)

                # Start new article
                article_number = article_match.group(1).replace('.', '').replace('-', '')
                article_title = article_match.group(2).strip()

                current_article = {
                    'article_number': article_number,
                    'article_title': f"Статья {article_number}. {article_title}",
                    'article_text': '',
                }
                current_paragraphs = []

            elif current_article and text:
                # Check if this is a numbered paragraph (starts with number and period)
                # Or if it's content following an article header
                paragraph_match = re.match(r'^(\d+)\.\s*(.+)$', text)

                if paragraph_match:
                    # This is a numbered paragraph
                    current_paragraphs.append(text)
                elif text and not text.startswith('Раздел') and not text.startswith('Глава') and not text.startswith('Подраздел'):
                    # This is article content
                    current_paragraphs.append(text)

        # Don't forget the last article
        if current_article and current_paragraphs:
            current_article['article_text'] = '\n\n'.join(current_paragraphs)
            articles.append(current_article)

        return {
            'code_id': code_id,
            'articles': articles,
            'source': 'kremlin.ru',
        }

    def save_base_articles(self, code_id: str, articles: List[Dict[str, Any]]) -> int:
        """
        Save base articles to code_article_versions table.

        Args:
            code_id: Code identifier
            articles: List of article dictionaries

        Returns:
            Number of articles saved
        """
        saved = 0

        for article in articles:
            try:
                with get_db_connection() as conn:
                    # Check if article already exists
                    check_query = text("""
                        SELECT id FROM code_article_versions
                        WHERE code_id = :code_id
                        AND article_number = :article_number
                        AND version_date = :version_date
                        LIMIT 1
                    """)
                    existing = conn.execute(check_query, {
                        'code_id': code_id,
                        'article_number': article['article_number'],
                        'version_date': CODE_METADATA[code_id]['original_date'],
                    }).fetchone()

                    if existing:
                        logger.debug(f"Article {article['article_number']} already exists, skipping")
                        continue

                    # Insert new article version
                    insert_query = text("""
                        INSERT INTO code_article_versions (
                            code_id,
                            article_number,
                            version_date,
                            article_text,
                            article_title,
                            amendment_eo_number,
                            amendment_date,
                            is_current,
                            is_repealed,
                            text_hash
                        ) VALUES (
                            :code_id,
                            :article_number,
                            :version_date,
                            :article_text,
                            :article_title,
                            :amendment_eo_number,
                            :amendment_date,
                            :is_current,
                            :is_repealed,
                            :text_hash
                        )
                    """)

                    conn.execute(insert_query, {
                        'code_id': code_id,
                        'article_number': article['article_number'],
                        'version_date': CODE_METADATA[code_id]['original_date'],
                        'article_text': article['article_text'],
                        'article_title': article['article_title'],
                        'amendment_eo_number': CODE_METADATA[code_id]['eo_number'],
                        'amendment_date': CODE_METADATA[code_id]['original_date'],
                        'is_current': True,  # Base version is current until amended
                        'is_repealed': False,
                        'text_hash': '',  # Will be computed by database trigger if needed
                    })
                    conn.commit()
                    saved += 1
                    logger.debug(f"Saved article {article['article_number']}")

            except Exception as e:
                logger.error(f"Failed to save article {article.get('article_number')}: {e}")

        return saved

    def import_code(self, code_id: str, source: str = 'auto') -> Dict[str, Any]:
        """
        Import a legal code from specified source.

        Automatically falls back to alternative sources if the primary is unavailable:
        - kremlin (official) -> pravo (official) -> consultant (reference)

        Args:
            code_id: Code identifier (e.g., 'TK_RF')
            source: Source to import from ('auto', 'kremlin', 'pravo', 'consultant')

        Returns:
            Result dictionary
        """
        if code_id not in CODE_METADATA:
            return {
                'code_id': code_id,
                'status': 'error',
                'error': f'Unknown code_id: {code_id}'
            }

        metadata = CODE_METADATA[code_id]

        # Auto-determine best available source
        if source == 'auto':
            sources_to_try = ['kremlin', 'pravo', 'consultant']
        else:
            sources_to_try = [source]

        # Try each source in priority order
        for src in sources_to_try:
            logger.info(f"Trying source: {src} for {code_id}")

            if src == 'kremlin':
                if metadata.get('kremlin_bank'):
                    html_pages = self.fetch_kremlin_html_all_pages(metadata['kremlin_bank'])
                    if html_pages:
                        parsed = self.parse_kremlin_html(html_pages, code_id)
                        articles = parsed.get('articles', [])
                        if articles:
                            # Articles from Kremlin already have full text
                            saved = self.save_base_articles(code_id, articles)
                            return {
                                'code_id': code_id,
                                'status': 'success',
                                'pages_fetched': len(html_pages),
                                'articles_found': len(articles),
                                'articles_processed': len(articles),
                                'articles_saved': saved,
                                'source': 'kremlin',
                            }

            elif src == 'pravo':
                # TODO: Implement pravo.gov.ru source
                logger.info(f"Pravo source not yet implemented, skipping")
                continue

            elif src == 'consultant':
                html = self.fetch_consultant_html(metadata['consultant_url'])
                if html:
                    parsed = self.parse_consultant_html(html, code_id)
                    articles = parsed.get('articles', [])
                    if articles:
                        # Fetch full text for each article
                        for i, article in enumerate(articles):
                            article['article_text'] = self.fetch_article_text(
                                article['article_url'],
                                article['article_number']
                            )
                            time.sleep(0.3)

                        saved = self.save_base_articles(code_id, articles)
                        return {
                            'code_id': code_id,
                            'status': 'success',
                            'articles_found': len(articles),
                            'articles_processed': len(articles),
                            'articles_saved': saved,
                            'source': 'consultant',
                        }

        # All sources failed
        return {
            'code_id': code_id,
            'status': 'error',
            'error': f'Failed to fetch from any source'
        }

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import base legal codes from official sources"
    )
    parser.add_argument(
        '--code',
        choices=list(CODE_METADATA.keys()),
        help='Code to import'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Import all codes'
    )
    parser.add_argument(
        '--source',
        choices=['auto', 'kremlin', 'pravo', 'consultant'],
        default='auto',
        help='Source to import from (default: auto - tries kremlin, then pravo, then consultant)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available codes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # Set UTF-8 for Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    # List codes
    if args.list:
        print("Available codes:")
        print("-" * 60)
        for code_id, metadata in CODE_METADATA.items():
            print(f"  {code_id}: {metadata['name']}")
            print(f"    EO Number: {metadata['eo_number']}")
            print(f"    Original Date: {metadata['original_date']}")
            print()
        return

    # Import codes
    with BaseCodeImporter() as importer:
        if args.code:
            result = importer.import_code(args.code, args.source)
            print(f"\n{'='*60}")
            print(f"Import Results: {result['code_id']}")
            print(f"{'='*60}")
            print(f"Status: {result['status']}")
            if result['status'] == 'success':
                if result.get('pages_fetched'):
                    print(f"Pages Fetched: {result['pages_fetched']}")
                print(f"Articles Found: {result['articles_found']}")
                print(f"Articles Processed: {result.get('articles_processed', 0)}")
                print(f"Articles Saved: {result['articles_saved']}")
                print(f"Source: {result['source']}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
            print(f"{'='*60}")

        elif args.all:
            print("Importing all codes...")
            results = []
            for code_id in CODE_METADATA.keys():
                result = importer.import_code(code_id, args.source)
                results.append(result)
                print(f"  {code_id}: {result['status']}")

            print(f"\n{'='*60}")
            print("Summary")
            print(f"{'='*60}")
            successful = sum(1 for r in results if r['status'] == 'success')
            print(f"Successful: {successful}/{len(results)}")

        else:
            parser.print_help()


if __name__ == "__main__":
    main()
