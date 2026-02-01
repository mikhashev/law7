"""
Article Number Parser for Russian Legal Documents

This module provides a robust parser for article numbers from Russian legal codes.
It handles various formats including:
- Simple articles: "25"
- Articles with insertions: "25.1", "25.12"
- Articles with subdivisions: "25-1"
- Complex combinations: "25.12-1"
- Large article numbers: "2512", "10516-1"

Usage:
    from scripts.core.article_parser import ArticleNumberParser

    parser = ArticleNumberParser()
    article = parser.parse("25.12-1")
    print(f"Base: {article.base}, Insertion: {article.insertion}, Subdivision: {article.subdivision}")
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class ArticleNumber:
    """
    Represents a structured article number with base, insertion, and subdivision.

    Attributes:
        base: The main article number (e.g., "25" in "25.12-1")
        insertion: Optional insertion point after decimal (e.g., "12" in "25.12-1")
        subdivision: Optional subdivision/appendix (e.g., "1" in "25.12-1")
    """
    base: int
    insertion: Optional[int] = None
    subdivision: Optional[int] = None

    def __str__(self) -> str:
        """Convert article number to standard string representation."""
        result = str(self.base)
        if self.insertion is not None:
            result += f".{self.insertion}"
        if self.subdivision is not None:
            result += f"-{self.subdivision}"
        return result

    def __repr__(self) -> str:
        """Return detailed representation for debugging."""
        return f"ArticleNumber(base={self.base}, insertion={self.insertion}, subdivision={self.subdivision})"

    def __eq__(self, other) -> bool:
        """Check equality based on all components."""
        if not isinstance(other, ArticleNumber):
            return False
        return (self.base == other.base and
                self.insertion == other.insertion and
                self.subdivision == other.subdivision)

    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((self.base, self.insertion, self.subdivision))

    def __lt__(self, other) -> bool:
        """Compare article numbers for less-than (for sorting)."""
        if not isinstance(other, ArticleNumber):
            return NotImplemented
        # Compare base first
        if self.base != other.base:
            # When comparing across different bases, if either has an insertion,
            # compare as decimal values (e.g., "23.1" vs "230" -> 23.1 vs 230)
            if self.insertion is not None or other.insertion is not None:
                self_val = self._to_decimal_value()
                other_val = other._to_decimal_value()
                return self_val < other_val
            return self.base < other.base
        # If base equal, compare insertion (None < 1 < 2, etc.)
        if self.insertion != other.insertion:
            if self.insertion is None:
                return True  # No insertion comes before having insertion
            if other.insertion is None:
                return False
            return self.insertion < other.insertion
        # If insertion equal, compare subdivision
        if self.subdivision != other.subdivision:
            if self.subdivision is None:
                return True
            if other.subdivision is None:
                return False
            return self.subdivision < other.subdivision
        return False  # Equal

    def _to_decimal_value(self) -> float:
        """
        Convert article number to decimal value for cross-base comparison.

        Articles with insertions are treated as decimals (e.g., "23.1" -> 23.1).
        This allows proper comparison like "230 < 23.1 < 232".

        Returns:
            Float value representing the article number
        """
        if self.insertion is not None:
            # Convert insertion to decimal (e.g., 1 -> 0.1, 12 -> 0.12, 123 -> 0.123)
            insertion_decimal = self.insertion / (10 ** len(str(self.insertion)))
            return float(self.base) + insertion_decimal
        return float(self.base)

    def __le__(self, other) -> bool:
        """Compare article numbers for less-than-or-equal."""
        if not isinstance(other, ArticleNumber):
            return NotImplemented
        return self == other or self < other

    def __gt__(self, other) -> bool:
        """Compare article numbers for greater-than."""
        if not isinstance(other, ArticleNumber):
            return NotImplemented
        return not self <= other

    def __ge__(self, other) -> bool:
        """Compare article numbers for greater-than-or-equal."""
        if not isinstance(other, ArticleNumber):
            return NotImplemented
        return not self < other

    def to_float_for_comparison(self) -> float:
        """
        Convert to float for range comparison purposes.

        Returns only the base number as float, which allows comparison
        against article ranges.

        Returns:
            Float value of the base article number
        """
        return float(self.base)


class ArticleNumberParser:
    r"""
    Complete article number parser with error handling.

    This parser handles the various article number formats found in Russian
    legal codes, including the Tax Code (NK_RF), Civil Code (GK_RF), and others.

    Regex Pattern: ^(\d+)(?:\.(\d+))?(?:-(\d+))?$
    - Group 1: Base article number (required)
    - Group 2: Insertion point after decimal (optional)
    - Group 3: Subdivision/appendix number (optional)
    """

    def __init__(self):
        """Initialize the parser with the article number regex pattern."""
        self.pattern = re.compile(r'^(\d+)(?:\.(\d+))?(?:-(\d+))?$')

    def parse(self, article_str: str) -> ArticleNumber:
        """
        Parse a single article number string into an ArticleNumber object.

        Args:
            article_str: Article number as string (e.g., "25", "25.12", "25.12-1")

        Returns:
            ArticleNumber object with parsed components

        Raises:
            ValueError: If the article number format is invalid

        Examples:
            >>> parser = ArticleNumberParser()
            >>> parser.parse("25")
            ArticleNumber(base=25, insertion=None, subdivision=None)
            >>> parser.parse("25.12")
            ArticleNumber(base=25, insertion=12, subdivision=None)
            >>> parser.parse("25.12-1")
            ArticleNumber(base=25, insertion=12, subdivision=1)
        """
        match = self.pattern.match(article_str)
        if not match:
            raise ValueError(f"Invalid article number format: '{article_str}'")

        base = int(match.group(1))
        insertion = int(match.group(2)) if match.group(2) else None
        subdivision = int(match.group(3)) if match.group(3) else None

        return ArticleNumber(base=base, insertion=insertion, subdivision=subdivision)

    def parse_bulk(
        self, article_list: List[str]
    ) -> Tuple[List[ArticleNumber], List[Tuple[str, str]]]:
        """
        Parse multiple article numbers, returning successes and failures.

        This is useful for batch processing article numbers from a document,
        where you want to track which articles failed to parse.

        Args:
            article_list: List of article number strings to parse

        Returns:
            Tuple of (successful_parses, failures)
            - successful_parses: List of ArticleNumber objects
            - failures: List of (article_str, error_message) tuples

        Examples:
            >>> parser = ArticleNumberParser()
            >>> articles = ["25", "invalid", "25.12-1"]
            >>> successes, failures = parser.parse_bulk(articles)
            >>> len(successes)
            2
            >>> len(failures)
            1
        """
        successes = []
        failures = []

        for article_str in article_list:
            try:
                parsed = self.parse(article_str)
                successes.append(parsed)
            except ValueError as e:
                failures.append((article_str, str(e)))

        return successes, failures

    def normalize(self, article_str: str) -> str:
        """
        Normalize an article number to standard format.

        Removes leading zeros and ensures consistent formatting.

        Args:
            article_str: Article number as string

        Returns:
            Normalized article number string

        Raises:
            ValueError: If the article number format is invalid

        Examples:
            >>> parser = ArticleNumberParser()
            >>> parser.normalize("025.01-1")
            '25.1-1'
            >>> parser.normalize("25.1")
            '25.1'
            >>> parser.normalize("025")
            '25'
        """
        parsed = self.parse(article_str)
        return str(parsed)

    def get_hierarchy(self, article_str: str) -> List[str]:
        """
        Get the hierarchical chain of article numbers.

        Returns the hierarchy from the base article down to the full article,
        which is useful for navigation and tree representation.

        Args:
            article_str: Article number as string

        Returns:
            List of article number strings representing the hierarchy

        Raises:
            ValueError: If the article number format is invalid

        Examples:
            >>> parser = ArticleNumberParser()
            >>> parser.get_hierarchy("25.12-1")
            ['25', '25.12', '25.12-1']
            >>> parser.get_hierarchy("25.1")
            ['25', '25.1']
            >>> parser.get_hierarchy("25")
            ['25']
        """
        parsed = self.parse(article_str)
        hierarchy = [str(parsed.base)]

        if parsed.insertion is not None:
            hierarchy.append(f"{parsed.base}.{parsed.insertion}")

        if parsed.subdivision is not None:
            hierarchy.append(str(parsed))

        return hierarchy

    def is_valid(self, article_str: str) -> bool:
        """
        Check if an article number string is valid without raising an exception.

        Args:
            article_str: Article number as string to validate

        Returns:
            True if the article number format is valid, False otherwise

        Examples:
            >>> parser = ArticleNumberParser()
            >>> parser.is_valid("25.12-1")
            True
            >>> parser.is_valid("invalid")
            False
        """
        try:
            self.parse(article_str)
            return True
        except ValueError:
            return False


# Singleton instance for convenience
_default_parser = None


def parse_article_number(article_str: str) -> ArticleNumber:
    """
    Convenience function to parse an article number using the default parser.

    Args:
        article_str: Article number as string

    Returns:
        ArticleNumber object with parsed components

    Raises:
        ValueError: If the article number format is invalid
    """
    global _default_parser
    if _default_parser is None:
        _default_parser = ArticleNumberParser()
    return _default_parser.parse(article_str)


def normalize_article_number(article_str: str) -> str:
    """
    Convenience function to normalize an article number using the default parser.

    Args:
        article_str: Article number as string

    Returns:
        Normalized article number string

    Raises:
        ValueError: If the article number format is invalid
    """
    global _default_parser
    if _default_parser is None:
        _default_parser = ArticleNumberParser()
    return _default_parser.normalize(article_str)
