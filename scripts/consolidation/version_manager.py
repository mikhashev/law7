"""
Version Manager for Russian Legal Code Articles.

This module tracks historical versions of articles:
- Store snapshot of each article after each amendment
- Enable queries like "What did Article X say on 2020-01-01?"
- Track amendment chain (which amendment changed what)
- Manage version history and current versions
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from scripts.core.db import get_db_connection, get_db_session
from scripts.consolidation.diff_engine import ArticleSnapshot

logger = logging.getLogger(__name__)


@dataclass
class VersionInfo:
    """Information about a specific version of an article."""
    article_number: str
    version_date: date
    amendment_eo_number: str
    is_current: bool
    is_repealed: bool
    text_hash: str = ""


@dataclass
class AmendmentChain:
    """Chain of amendments affecting an article."""
    article_number: str
    versions: List[VersionInfo] = field(default_factory=list)
    current_version: Optional[VersionInfo] = None

    def get_version_on_date(self, query_date: date) -> Optional[VersionInfo]:
        """Get the version of this article that was in effect on a specific date."""
        # Filter versions that were in effect on query_date
        valid_versions = [
            v for v in self.versions
            if v.version_date <= query_date
        ]

        if not valid_versions:
            return None

        # Return the most recent version before query_date
        return max(valid_versions, key=lambda v: v.version_date)


class VersionManager:
    """
    Manages version history of legal code articles.

    Stores and retrieves historical versions from the database.
    """

    def __init__(self):
        """Initialize the version manager."""
        self.cache: Dict[str, AmendmentChain] = {}

    def save_snapshot(
        self,
        code_id: str,
        snapshot: ArticleSnapshot,
        conn=None,
    ) -> bool:
        """
        Save a snapshot of an article to the database.

        Args:
            code_id: Code identifier (e.g., 'TK_RF', 'GK_RF')
            snapshot: Article snapshot to save
            conn: Optional database connection

        Returns:
            True if save successful, False otherwise
        """
        import hashlib

        text_hash = hashlib.md5(snapshot.article_text.encode('utf-8')).hexdigest()

        try:
            if conn is None:
                # Use connection from context manager
                with get_db_connection() as conn:
                    self._insert_snapshot(conn, code_id, snapshot, text_hash)
            else:
                self._insert_snapshot(conn, code_id, snapshot, text_hash)

            logger.debug(f"Saved snapshot for article {snapshot.article_number} of {code_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return False

    def _insert_snapshot(self, conn, code_id: str, snapshot: ArticleSnapshot, text_hash: str):
        """Insert snapshot into database."""
        query = text("""
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
                repealed_date,
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
                :repealed_date,
                :text_hash
            )
            ON CONFLICT (code_id, article_number, version_date) DO UPDATE
            SET
                article_text = EXCLUDED.article_text,
                article_title = EXCLUDED.article_title,
                amendment_eo_number = EXCLUDED.amendment_eo_number,
                is_current = EXCLUDED.is_current,
                is_repealed = EXCLUDED.is_repealed,
                repealed_date = EXCLUDED.repealed_date,
                text_hash = EXCLUDED.text_hash
        """)

        conn.execute(query, {
            'code_id': code_id,
            'article_number': snapshot.article_number,
            'version_date': snapshot.version_date,
            'article_text': snapshot.article_text,
            'article_title': snapshot.article_title,
            'amendment_eo_number': snapshot.amendment_eo_number,
            'amendment_date': snapshot.version_date,
            'is_current': snapshot.is_current,
            'is_repealed': snapshot.is_repealed,
            'repealed_date': snapshot.repealed_date,
            'text_hash': text_hash,
        })
        conn.commit()

    def get_current_version(
        self,
        code_id: str,
        article_number: str,
    ) -> Optional[ArticleSnapshot]:
        """
        Get the current version of an article.

        Args:
            code_id: Code identifier (e.g., 'TK_RF')
            article_number: Article number

        Returns:
            ArticleSnapshot or None if not found
        """
        cache_key = f"{code_id}:{article_number}"

        if cache_key in self.cache:
            chain = self.cache[cache_key]
            if chain.current_version:
                return self._version_info_to_snapshot(article_number, chain.current_version)

        query = text("""
            SELECT
                article_number,
                article_title,
                article_text,
                version_date,
                amendment_eo_number,
                is_current,
                is_repealed,
                repealed_date
            FROM code_article_versions
            WHERE code_id = :code_id
            AND article_number = :article_number
            AND is_current = true
            ORDER BY version_date DESC
            LIMIT 1
        """)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query, {
                    'code_id': code_id,
                    'article_number': article_number,
                })

                row = result.fetchone()
                if row:
                    return ArticleSnapshot(
                        article_number=row[0],
                        article_title=row[1] or "",
                        article_text=row[2] or "",
                        version_date=row[3],
                        amendment_eo_number=row[4] or "",
                        is_current=row[5],
                        is_repealed=row[6] or False,
                        repealed_date=row[7],
                    )
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")

        return None

    def get_version_on_date(
        self,
        code_id: str,
        article_number: str,
        query_date: date,
    ) -> Optional[ArticleSnapshot]:
        """
        Get the version of an article that was in effect on a specific date.

        Args:
            code_id: Code identifier
            article_number: Article number
            query_date: Date to query

        Returns:
            ArticleSnapshot as of query_date, or None if not found
        """
        query = text("""
            SELECT
                article_number,
                article_title,
                article_text,
                version_date,
                amendment_eo_number,
                is_current,
                is_repealed,
                repealed_date
            FROM code_article_versions
            WHERE code_id = :code_id
            AND article_number = :article_number
            AND version_date <= :query_date
            ORDER BY version_date DESC
            LIMIT 1
        """)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query, {
                    'code_id': code_id,
                    'article_number': article_number,
                    'query_date': query_date,
                })

                row = result.fetchone()
                if row:
                    return ArticleSnapshot(
                        article_number=row[0],
                        article_title=row[1] or "",
                        article_text=row[2] or "",
                        version_date=row[3],
                        amendment_eo_number=row[4] or "",
                        is_current=row[5],
                        is_repealed=row[6] or False,
                        repealed_date=row[7],
                    )
        except Exception as e:
            logger.error(f"Failed to get version on date: {e}")

        return None

    def get_amendment_chain(
        self,
        code_id: str,
        article_number: str,
    ) -> AmendmentChain:
        """
        Get the full amendment chain for an article.

        Args:
            code_id: Code identifier
            article_number: Article number

        Returns:
            AmendmentChain with all versions
        """
        query = text("""
            SELECT
                version_date,
                amendment_eo_number,
                is_current,
                is_repealed,
                text_hash
            FROM code_article_versions
            WHERE code_id = :code_id
            AND article_number = :article_number
            ORDER BY version_date ASC
        """)

        chain = AmendmentChain(article_number=article_number)

        try:
            with get_db_connection() as conn:
                result = conn.execute(query, {
                    'code_id': code_id,
                    'article_number': article_number,
                })

                for row in result:
                    version_info = VersionInfo(
                        article_number=article_number,
                        version_date=row[0],
                        amendment_eo_number=row[1] or "",
                        is_current=row[2],
                        is_repealed=row[3] or False,
                        text_hash=row[4] or "",
                    )
                    chain.versions.append(version_info)
                    if row[2]:  # is_current
                        chain.current_version = version_info
        except Exception as e:
            logger.error(f"Failed to get amendment chain: {e}")

        return chain

    def mark_old_versions_as_not_current(
        self,
        code_id: str,
        article_number: str,
        new_version_date: date,
        conn=None,
    ):
        """
        Mark older versions of an article as not current.

        Args:
            code_id: Code identifier
            article_number: Article number
            new_version_date: Date of new version
            conn: Optional database connection
        """
        query = text("""
            UPDATE code_article_versions
            SET is_current = false
            WHERE code_id = :code_id
            AND article_number = :article_number
            AND version_date < :new_version_date
        """)

        try:
            if conn is None:
                with get_db_connection() as conn:
                    conn.execute(query, {
                        'code_id': code_id,
                        'article_number': article_number,
                        'new_version_date': new_version_date,
                    })
                    conn.commit()
            else:
                conn.execute(query, {
                    'code_id': code_id,
                    'article_number': article_number,
                    'new_version_date': new_version_date,
                })

            logger.debug(f"Marked old versions of {code_id}:{article_number} as not current")

        except Exception as e:
            logger.error(f"Failed to mark old versions: {e}")

    def _version_info_to_snapshot(
        self,
        article_number: str,
        version_info: VersionInfo,
    ) -> ArticleSnapshot:
        """Convert VersionInfo to ArticleSnapshot."""
        return ArticleSnapshot(
            article_number=article_number,
            version_date=version_info.version_date,
            amendment_eo_number=version_info.amendment_eo_number,
            is_current=version_info.is_current,
            is_repealed=version_info.is_repealed,
            repealed_date=version_info.repealed_date,
        )


def get_article_history(
    code_id: str,
    article_number: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Get version history for an article within a date range.

    Args:
        code_id: Code identifier
        article_number: Article number
        start_date: Optional start date
        end_date: Optional end date

    Returns:
        List of version dictionaries
    """
    query = """
        SELECT
            version_date,
            amendment_eo_number,
            is_current,
            is_repealed,
            article_title,
            LEFT(article_text, 100) as text_preview
        FROM code_article_versions
        WHERE code_id = :code_id
        AND article_number = :article_number
    """

    params = {'code_id': code_id, 'article_number': article_number}

    if start_date:
        query += " AND version_date >= :start_date"
        params['start_date'] = start_date

    if end_date:
        query += " AND version_date <= :end_date"
        params['end_date'] = end_date

    query += " ORDER BY version_date DESC"

    try:
        with get_db_connection() as conn:
            result = conn.execute(text(query), params)
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result]
    except Exception as e:
        logger.error(f"Failed to get article history: {e}")
        return []
