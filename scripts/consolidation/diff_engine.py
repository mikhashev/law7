"""
Article Diff Engine for Russian Legal Codes.

This module applies amendments to article text:
- Modifications: Replace old text with new text
- Additions: Insert new article (or renumber subsequent articles)
- Repeals: Mark article as repealed with effective date
- Conflicts: Handle multiple amendments affecting same article

The engine maintains version history for each article.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class ArticleSnapshot:
    """Represents a snapshot of an article at a point in time."""
    article_number: str
    article_title: str = ""
    article_text: str = ""
    version_date: date = None
    amendment_eo_number: str = ""
    is_current: bool = True
    is_repealed: bool = False
    repealed_date: Optional[date] = None


@dataclass
class DiffResult:
    """Result of applying a diff operation."""
    success: bool
    article_number: str
    old_text: str = ""
    new_text: str = ""
    changes_made: int = 0
    error_message: str = ""


class ArticleDiffEngine:
    """
    Engine for applying amendments to legal code articles.

    Handles various types of changes:
    - Text replacements (word/phrase substitutions)
    - Article additions (insert new, renumber existing)
    - Article repeals (mark as no longer valid)
    - Complex changes (combinations of above)
    """

    def __init__(self):
        """Initialize the diff engine."""
        self.renumbering_map: Dict[str, str] = {}  # Track article renumbering

    def apply_text_replacement(
        self,
        article_text: str,
        old_text: str,
        new_text: str,
    ) -> DiffResult:
        """
        Apply text replacement to an article.

        Args:
            article_text: Original article text
            old_text: Text to replace
            new_text: Replacement text

        Returns:
            DiffResult with the modified text
        """
        if old_text not in article_text:
            # Try fuzzy matching
            new_article_text = self._fuzzy_replace(article_text, old_text, new_text)
            if new_article_text == article_text:
                return DiffResult(
                    success=False,
                    article_number="",
                    old_text=article_text,
                    error_message=f"Old text not found in article",
                )
            article_text = new_article_text
        else:
            article_text = article_text.replace(old_text, new_text, 1)

        return DiffResult(
            success=True,
            article_number="",
            old_text=article_text,
            new_text=article_text,
            changes_made=1,
        )

    def apply_addition(
        self,
        current_articles: Dict[str, ArticleSnapshot],
        new_article_number: str,
        new_article_text: str,
        new_article_title: str = "",
        version_date: date = None,
        amendment_eo_number: str = "",
    ) -> tuple[Dict[str, ArticleSnapshot], List[str]]:
        """
        Add a new article to the code.

        When adding an article, subsequent articles may need to be renumbered.

        Args:
            current_articles: Current article snapshots
            new_article_number: Article number to add
            new_article_text: Text of new article
            new_article_title: Title of new article
            version_date: When this change takes effect
            amendment_eo_number: Amendment making this change

        Returns:
            Tuple of (updated articles, list of renumbered articles)
        """
        # Check if article already exists
        if new_article_number in current_articles:
            logger.warning(f"Article {new_article_number} already exists, updating instead")
            current_articles[new_article_number] = ArticleSnapshot(
                article_number=new_article_number,
                article_title=new_article_title,
                article_text=new_article_text,
                version_date=version_date or date.today(),
                amendment_eo_number=amendment_eo_number,
                is_current=True,
            )
            return current_articles, []

        # Add new article
        new_snapshot = ArticleSnapshot(
            article_number=new_article_number,
            article_title=new_article_title,
            article_text=new_article_text,
            version_date=version_date or date.today(),
            amendment_eo_number=amendment_eo_number,
            is_current=True,
        )

        # Insert article in correct position
        current_articles[new_article_number] = new_snapshot

        # Note: Actual renumbering would require parsing all article numbers
        # and shifting subsequent ones. This is complex and is handled separately.

        return current_articles, []

    def apply_repeal(
        self,
        current_articles: Dict[str, ArticleSnapshot],
        article_number: str,
        repeal_date: date,
        amendment_eo_number: str = "",
    ) -> Dict[str, ArticleSnapshot]:
        """
        Repeal an article (mark as no longer valid).

        Args:
            current_articles: Current article snapshots
            article_number: Article to repeal
            repeal_date: When repeal takes effect
            amendment_eo_number: Amendment making this repeal

        Returns:
            Updated articles with the specified article repealed
        """
        if article_number not in current_articles:
            logger.warning(f"Cannot repeal article {article_number}: not found")
            return current_articles

        # Mark as repealed but keep the text
        article = current_articles[article_number]
        article.is_repealed = True
        article.repealed_date = repeal_date
        article.is_current = False
        article.amendment_eo_number = amendment_eo_number

        current_articles[article_number] = article
        return current_articles

    def apply_complex_change(
        self,
        article_text: str,
        changes: List[Dict[str, str]],
    ) -> DiffResult:
        """
        Apply complex changes with multiple operations.

        Args:
            article_text: Original article text
            changes: List of change operations, each with:
                     - type: 'replace', 'add', 'remove'
                     - old: Old text (for replace/remove)
                     - new: New text (for replace/add)
                     - position: Optional position for insertions

        Returns:
            DiffResult with the modified text
        """
        result_text = article_text
        changes_applied = 0

        for change in changes:
            change_type = change.get('type', '')
            old = change.get('old', '')
            new = change.get('new', '')

            if change_type == 'replace':
                if old in result_text:
                    result_text = result_text.replace(old, new, 1)
                    changes_applied += 1
            elif change_type == 'add':
                position = change.get('position')
                if position is not None:
                    # Insert at specific position
                    result_text = result_text[:position] + new + result_text[position:]
                else:
                    # Append to end
                    result_text = result_text + "\n" + new
                changes_applied += 1
            elif change_type == 'remove':
                if old in result_text:
                    result_text = result_text.replace(old, '', 1)
                    changes_applied += 1

        return DiffResult(
            success=changes_applied > 0,
            article_number="",
            old_text=article_text,
            new_text=result_text,
            changes_made=changes_applied,
        )

    def create_snapshot(
        self,
        article_number: str,
        article_text: str,
        article_title: str = "",
        version_date: date = None,
        amendment_eo_number: str = "",
        is_current: bool = True,
    ) -> ArticleSnapshot:
        """
        Create a snapshot of an article at a point in time.

        Args:
            article_number: Article identifier
            article_text: Full article text
            article_title: Article title
            version_date: When this version takes effect
            amendment_eo_number: Amendment that created this version
            is_current: Whether this is the current version

        Returns:
            ArticleSnapshot object
        """
        return ArticleSnapshot(
            article_number=article_number,
            article_title=article_title,
            article_text=article_text,
            version_date=version_date or date.today(),
            amendment_eo_number=amendment_eo_number,
            is_current=is_current,
        )

    def compare_versions(
        self,
        old_version: ArticleSnapshot,
        new_version: ArticleSnapshot,
    ) -> Dict[str, Any]:
        """
        Compare two versions of an article and highlight differences.

        Args:
            old_version: Previous article version
            new_version: New article version

        Returns:
            Dictionary with comparison results:
                - changes_detected: bool
                - changes: List of change descriptions
                - similarity: float (0-1)
        """
        if old_version.article_number != new_version.article_number:
            return {
                'changes_detected': True,
                'changes': [f"Different articles: {old_version.article_number} vs {new_version.article_number}"],
                'similarity': 0.0,
            }

        old_text = old_version.article_text
        new_text = new_version.article_text

        # Calculate similarity using SequenceMatcher
        matcher = SequenceMatcher(None, old_text, new_text)
        similarity = matcher.ratio()

        changes = []

        # Check for repealed status change
        if old_version.is_repealed != new_version.is_repealed:
            if new_version.is_repealed:
                changes.append(f"Article repealed on {new_version.repealed_date}")
            else:
                changes.append("Article reinstated")

        # Check for text changes
        if old_text != new_text:
            # Get the differences
            opcodes = matcher.get_opcodes()
            for tag, i1, i2, j1, j2 in opcodes:
                if tag == 'replace':
                    changes.append(f"Replaced: '{old_text[i1:i2][:50]}...' with '{new_text[j1:j2][:50]}...'")
                elif tag == 'delete':
                    changes.append(f"Deleted: '{old_text[i1:i2][:50]}...'")
                elif tag == 'insert':
                    changes.append(f"Inserted: '{new_text[j1:j2][:50]}...'")

        return {
            'changes_detected': len(changes) > 0,
            'changes': changes,
            'similarity': similarity,
        }

    def _fuzzy_replace(
        self,
        text: str,
        old: str,
        new: str,
        threshold: float = 0.8,
    ) -> str:
        """
        Replace text with fuzzy matching.

        Args:
            text: Text to search in
            old: Text to search for (with fuzzy matching)
            new: Replacement text
            threshold: Similarity threshold (0-1)

        Returns:
            Text with replacements made
        """
        # Split text into words for matching
        words = text.split()
        old_words = old.split()

        # Try to find approximate match
        for i in range(len(words) - len(old_words) + 1):
            segment = ' '.join(words[i:i + len(old_words)])
            matcher = SequenceMatcher(None, segment, old)
            if matcher.ratio() >= threshold:
                # Replace this segment
                words[i:i + len(old_words)] = [new]
                return ' '.join(words)

        return text


def apply_amendment_to_article(
    article: ArticleSnapshot,
    amendment_type: str,
    amendment_data: Dict[str, Any],
) -> ArticleSnapshot:
    """
    Apply an amendment to an article snapshot.

    Convenience function for single-article amendments.

    Args:
        article: Current article snapshot
        amendment_type: Type of amendment ('modification', 'addition', 'repeal')
        amendment_data: Amendment details:
                         - old_text: For modifications
                         - new_text: For modifications/additions
                         - repeal_date: For repeals
                         - amendment_eo_number: Source amendment
                         - effective_date: When change takes effect

    Returns:
        New ArticleSnapshot with amendment applied
    """
    engine = ArticleDiffEngine()

    if amendment_type == 'modification':
        result = engine.apply_text_replacement(
            article.article_text,
            amendment_data.get('old_text', ''),
            amendment_data.get('new_text', ''),
        )
        if result.success:
            article.article_text = result.new_text

    elif amendment_type == 'repeal':
        articles = {article.article_number: article}
        articles = engine.apply_repeal(
            articles,
            article.article_number,
            amendment_data.get('repeal_date', date.today()),
            amendment_data.get('amendment_eo_number', ''),
        )
        article = articles[article.article_number]

    # Update metadata
    article.amendment_eo_number = amendment_data.get('amendment_eo_number', '')
    article.version_date = amendment_data.get('effective_date', date.today())

    return article
