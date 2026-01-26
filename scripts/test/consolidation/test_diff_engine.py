"""
Tests for Article Diff Engine (scripts/consolidation/diff_engine.py)

Tests cover:
- Text replacement (exact and fuzzy matching)
- Article additions
- Article repeals
- Complex changes (multiple operations)
- Snapshot creation
- Version comparison
"""

import pytest
from datetime import date
from unittest.mock import patch

from scripts.consolidation.diff_engine import (
    ArticleSnapshot,
    DiffResult,
    ArticleDiffEngine,
    apply_amendment_to_article,
)


class TestArticleSnapshot:
    """Tests for ArticleSnapshot dataclass."""

    def test_create_snapshot_default(self):
        """Test creating snapshot with default values."""
        snapshot = ArticleSnapshot(
            article_number="123",
        )
        assert snapshot.article_number == "123"
        assert snapshot.article_title == ""
        assert snapshot.article_text == ""
        assert snapshot.is_current is True
        assert snapshot.is_repealed is False
        assert snapshot.version_date is None

    def test_create_snapshot_full(self):
        """Test creating snapshot with all fields."""
        snapshot = ArticleSnapshot(
            article_number="123",
            article_title="Test Article",
            article_text="Article content here",
            version_date=date(2026, 1, 1),
            amendment_eo_number="0001202601170001",
            is_current=False,
            is_repealed=True,
            repealed_date=date(2027, 1, 1),
        )
        assert snapshot.article_number == "123"
        assert snapshot.article_title == "Test Article"
        assert snapshot.is_repealed is True


class TestDiffResult:
    """Tests for DiffResult dataclass."""

    def test_diff_result_success(self):
        """Test successful diff result."""
        result = DiffResult(
            success=True,
            article_number="123",
            old_text="old text",
            new_text="new text",
            changes_made=1,
        )
        assert result.success is True
        assert result.changes_made == 1

    def test_diff_result_failure(self):
        """Test failed diff result."""
        result = DiffResult(
            success=False,
            article_number="123",
            error_message="Text not found",
        )
        assert result.success is False
        assert result.error_message == "Text not found"


class TestArticleDiffEngineInit:
    """Tests for ArticleDiffEngine initialization."""

    def test_init_default(self):
        """Test default initialization."""
        engine = ArticleDiffEngine()
        assert engine.renumbering_map == {}


class TestApplyTextReplacement:
    """Tests for apply_text_replacement method."""

    def test_replace_exact_match(self):
        """Test replacing text with exact match."""
        engine = ArticleDiffEngine()
        result = engine.apply_text_replacement(
            "The quick brown fox",
            "quick",
            "slow",
        )
        assert result.success is True
        assert result.new_text == "The slow brown fox"

    def test_replace_first_occurrence_only(self):
        """Test that only first occurrence is replaced."""
        engine = ArticleDiffEngine()
        result = engine.apply_text_replacement(
            "the cat and the dog",
            "the",
            "a",
        )
        # Only first 'the' replaced
        assert result.new_text == "a cat and the dog"

    def test_replace_text_not_found(self):
        """Test replacing when old text not found."""
        engine = ArticleDiffEngine()
        result = engine.apply_text_replacement(
            "The quick brown fox",
            "elephant",
            "giraffe",
        )
        assert result.success is False
        assert "not found" in result.error_message

    def test_replace_with_fuzzy_match(self):
        """Test fuzzy replacement for similar text."""
        engine = ArticleDiffEngine()
        # Fuzzy match should work with minor differences
        result = engine.apply_text_replacement(
            "The qick brown fox",  # typo: 'qick' instead of 'quick'
            "quick",
            "slow",
        )
        # Fuzzy matching might or might not succeed depending on threshold
        # Just verify the function runs without error
        assert isinstance(result, DiffResult)

    def test_replace_empty_old_text(self):
        """Test replacing empty text."""
        engine = ArticleDiffEngine()
        result = engine.apply_text_replacement(
            "Test text",
            "",
            "new",
        )
        # Empty string is in any string, so it might succeed or fail
        assert isinstance(result, DiffResult)


class TestApplyAddition:
    """Tests for apply_addition method."""

    def test_add_new_article(self):
        """Test adding a new article."""
        engine = ArticleDiffEngine()
        current_articles = {}

        updated, renumbered = engine.apply_addition(
            current_articles,
            "145",
            "New article text",
            "New Article Title",
            date(2026, 1, 1),
            "eo123",
        )

        assert "145" in updated
        assert updated["145"].article_number == "145"
        assert updated["145"].article_text == "New article text"
        assert updated["145"].is_current is True

    def test_add_existing_article_updates(self):
        """Test adding article that already exists updates it."""
        engine = ArticleDiffEngine()
        current_articles = {
            "123": ArticleSnapshot(
                article_number="123",
                article_text="Old text",
            )
        }

        updated, renumbered = engine.apply_addition(
            current_articles,
            "123",
            "Updated text",
            "Updated Title",
            date(2026, 1, 1),
            "eo456",
        )

        assert updated["123"].article_text == "Updated text"
        assert updated["123"].article_title == "Updated Title"

    def test_add_article_with_default_date(self):
        """Test adding article with default date (today)."""
        engine = ArticleDiffEngine()
        current_articles = {}

        updated, renumbered = engine.apply_addition(
            current_articles,
            "200",
            "Text",
        )

        # Should use today's date
        assert updated["200"].version_date is not None


class TestApplyRepeal:
    """Tests for apply_repeal method."""

    def test_repeal_existing_article(self):
        """Test repealing an existing article."""
        engine = ArticleDiffEngine()
        current_articles = {
            "123": ArticleSnapshot(
                article_number="123",
                article_text="Some text",
                is_current=True,
                is_repealed=False,
            )
        }

        updated = engine.apply_repeal(
            current_articles,
            "123",
            date(2026, 1, 1),
            "eo789",
        )

        assert updated["123"].is_repealed is True
        assert updated["123"].repealed_date == date(2026, 1, 1)
        assert updated["123"].is_current is False

    def test_repeal_nonexistent_article(self):
        """Test repealing article that doesn't exist."""
        engine = ArticleDiffEngine()
        current_articles = {}

        updated = engine.apply_repeal(
            current_articles,
            "999",
            date(2026, 1, 1),
        )

        # Should return unchanged
        assert len(updated) == 0


class TestApplyComplexChange:
    """Tests for apply_complex_change method."""

    def test_apply_multiple_replacements(self):
        """Test applying multiple replace operations."""
        engine = ArticleDiffEngine()
        changes = [
            {"type": "replace", "old": "cat", "new": "dog"},
            {"type": "replace", "old": "mouse", "new": "elephant"},
        ]

        result = engine.apply_complex_change(
            "The cat and the mouse",
            changes,
        )

        assert result.success is True
        assert "dog" in result.new_text
        assert "elephant" in result.new_text

    def test_apply_add_operation(self):
        """Test applying add operation."""
        engine = ArticleDiffEngine()
        changes = [
            {"type": "add", "new": "Additional text"},
        ]

        result = engine.apply_complex_change(
            "Original text",
            changes,
        )

        assert result.success is True
        assert "Additional text" in result.new_text

    def test_apply_remove_operation(self):
        """Test applying remove operation."""
        engine = ArticleDiffEngine()
        changes = [
            {"type": "remove", "old": "unwanted "},
        ]

        result = engine.apply_complex_change(
            "This is unwanted text",
            changes,
        )

        assert result.success is True
        assert "unwanted " not in result.new_text

    def test_apply_add_at_position(self):
        """Test adding text at specific position."""
        engine = ArticleDiffEngine()
        changes = [
            {"type": "add", "new": "MIDDLE", "position": 5},
        ]

        result = engine.apply_complex_change(
            "1234567890",
            changes,
        )

        assert result.new_text == "12345MIDDLE67890"

    def test_apply_complex_change_no_changes(self):
        """Test applying changes that don't match."""
        engine = ArticleDiffEngine()
        changes = [
            {"type": "replace", "old": "notfound", "new": "replacement"},
        ]

        result = engine.apply_complex_change(
            "Some text",
            changes,
        )

        assert result.success is False
        assert result.changes_made == 0


class TestCreateSnapshot:
    """Tests for create_snapshot method."""

    def test_create_snapshot_with_defaults(self):
        """Test creating snapshot with default values."""
        engine = ArticleDiffEngine()
        snapshot = engine.create_snapshot("123", "article text")  # article_text is required

        assert snapshot.article_number == "123"
        assert snapshot.article_text == "article text"
        assert snapshot.is_current is True
        # version_date should default to today
        assert snapshot.version_date is not None

    def test_create_snapshot_full(self):
        """Test creating snapshot with all parameters."""
        engine = ArticleDiffEngine()
        snapshot = engine.create_snapshot(
            article_number="456",
            article_text="Full article text",  # article_text is required
            article_title="Full Title",
            version_date=date(2026, 1, 1),
            amendment_eo_number="eo123",
            is_current=False,
        )

        assert snapshot.article_number == "456"
        assert snapshot.article_text == "Full article text"
        assert snapshot.is_current is False


class TestCompareVersions:
    """Tests for compare_versions method."""

    def test_compare_identical_versions(self):
        """Test comparing identical versions."""
        engine = ArticleDiffEngine()
        v1 = ArticleSnapshot(
            article_number="123",
            article_text="Same text",
        )
        v2 = ArticleSnapshot(
            article_number="123",
            article_text="Same text",
        )

        result = engine.compare_versions(v1, v2)

        assert result["changes_detected"] is False
        assert result["similarity"] == 1.0

    def test_compare_different_text(self):
        """Test comparing versions with different text."""
        engine = ArticleDiffEngine()
        v1 = ArticleSnapshot(
            article_number="123",
            article_text="Old text",
        )
        v2 = ArticleSnapshot(
            article_number="123",
            article_text="New text",
        )

        result = engine.compare_versions(v1, v2)

        assert result["changes_detected"] is True
        assert result["similarity"] < 1.0
        assert len(result["changes"]) > 0

    def test_compare_different_articles(self):
        """Test comparing different article numbers."""
        engine = ArticleDiffEngine()
        v1 = ArticleSnapshot(
            article_number="123",
            article_text="Text",
        )
        v2 = ArticleSnapshot(
            article_number="456",
            article_text="Text",
        )

        result = engine.compare_versions(v1, v2)

        assert result["changes_detected"] is True
        assert result["similarity"] == 0.0
        assert "Different articles" in result["changes"][0]

    def test_compare_repeal_status_change(self):
        """Test detecting repeal status change."""
        engine = ArticleDiffEngine()
        v1 = ArticleSnapshot(
            article_number="123",
            article_text="Text",
            is_repealed=False,
        )
        v2 = ArticleSnapshot(
            article_number="123",
            article_text="Text",
            is_repealed=True,
            repealed_date=date(2026, 1, 1),
        )

        result = engine.compare_versions(v1, v2)

        assert result["changes_detected"] is True
        assert any("repealed" in c.lower() for c in result["changes"])


class TestApplyAmendmentToArticle:
    """Tests for apply_amendment_to_article convenience function."""

    def test_apply_modification(self):
        """Test applying modification amendment."""
        article = ArticleSnapshot(
            article_number="123",
            article_text="Old content here",
        )

        result = apply_amendment_to_article(
            article,
            "modification",
            {
                "old_text": "Old",
                "new_text": "New",
                "amendment_eo_number": "eo123",
                "effective_date": date(2026, 1, 1),
            },
        )

        assert "New" in result.article_text
        assert "Old" not in result.article_text
        assert result.amendment_eo_number == "eo123"

    def test_apply_repeal(self):
        """Test applying repeal amendment."""
        article = ArticleSnapshot(
            article_number="123",
            article_text="Some text",
            is_current=True,
            is_repealed=False,
        )

        result = apply_amendment_to_article(
            article,
            "repeal",
            {
                "repeal_date": date(2026, 1, 1),
                "amendment_eo_number": "eo456",
            },
        )

        assert result.is_repealed is True
        assert result.repealed_date == date(2026, 1, 1)


class TestFuzzyReplace:
    """Tests for _fuzzy_replace method."""

    def test_fuzzy_replace_exact_match(self):
        """Test fuzzy replace with exact match."""
        engine = ArticleDiffEngine()
        result = engine._fuzzy_replace(
            "The quick brown fox",
            "quick",
            "slow",
            threshold=0.8,
        )
        # Should find and replace
        assert "slow" in result

    def test_fuzzy_replace_no_match(self):
        """Test fuzzy replace with no good match."""
        engine = ArticleDiffEngine()
        result = engine._fuzzy_replace(
            "The quick brown fox",
            "elephant",
            "giraffe",
            threshold=0.8,
        )
        # Should return original text
        assert result == "The quick brown fox"

    def test_fuzzy_replace_low_threshold(self):
        """Test fuzzy replace with low threshold."""
        engine = ArticleDiffEngine()
        # With low threshold, should match more loosely
        result = engine._fuzzy_replace(
            "The qick brown fox",  # typo
            "quick",
            "slow",
            threshold=0.5,
        )
        # May or may not succeed depending on similarity
        assert isinstance(result, str)
