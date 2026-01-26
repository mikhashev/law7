"""
Amendment Parser for Russian Legal Codes.

This module parses amendment text to extract:
- Target articles (which articles are affected)
- Action type (addition, modification, repeal)
- New text content
- Effective date

Example amendment patterns:
- "В статье 123 Трудового кодекса..." (In article 123 of Labor Code...)
- "Дополнить статьей 1451..." (Add article 1451...)
- "Признать утратившим силу статью 5..." (Repeal article 5...)

This is the Russia-specific parser for Russian legal amendment text.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Country identification
country_id = "RUS"
country_name = "Russia"
country_code = "RU"


@dataclass
class AmendmentTarget:
    """Represents what an amendment affects."""
    code_id: str  # 'GK_RF', 'UK_RF', 'TK_RF', etc.
    code_name: str  # 'Гражданский кодекс', 'Уголовный кодекс', etc.
    articles_affected: List[str] = field(default_factory=list)  # ['123', '456', '789']
    is_full_code: bool = False  # True if entire code is affected


@dataclass
class AmendmentChange:
    """Represents a single change made by an amendment."""
    action_type: str  # 'addition', 'modification', 'repeal', 'reorganization'
    article_number: Optional[str] = None  # '123' or None if full code
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    context: str = ""  # Surrounding text for reference


@dataclass
class ParsedAmendment:
    """Represents a fully parsed amendment."""
    eo_number: str  # Amendment document number
    title: str  # Amendment title
    code_id: str  # Target code identifier
    code_name: str  # Target code name
    action_type: str  # 'addition', 'modification', 'repeal', 'mixed'
    changes: List[AmendmentChange] = field(default_factory=list)
    effective_date: Optional[datetime] = None
    raw_text: str = ""  # Original amendment text


# Code name to ID mapping
CODE_PATTERNS = {
    'TK_RF': ['Трудовой кодекс', 'ТК РФ', 'Трудового кодекса'],
    'GK_RF': ['Гражданский кодекс', 'ГК РФ', 'Гражданского кодекса'],
    'UK_RF': ['Уголовный кодекс', 'УК РФ', 'Уголовного кодекса'],
    'NK_RF': ['Налоговый кодекс', 'НК РФ', 'Налогового кодекса'],
    'KoAP_RF': ['КоАП', 'Кодекс об административных', 'административных правонарушениях'],
    'SK_RF': ['Семейный кодекс', 'СК РФ', 'Семейного кодекса'],
    'ZhK_RF': ['Жилищный кодекс', 'ЖК РФ', 'Жилищного кодекса'],
    'ZK_RF': ['Земельный кодекс', 'ЗК РФ', 'Земельного кодекса'],
    # Add more codes as needed
}


class AmendmentParser:
    """
    Parser for Russian legal amendment text (Russia).

    This is the Russia-specific parser for extracting structured information
    about which articles are changed and what those changes are.
    """

    # Country identification
    country_id = "RUS"
    country_name = "Russia"
    country_code = "RU"

    # Patterns for matching article references
    ARTICLE_PATTERNS = [
        r'стать(?:я|и|ю|е) (\d+(?:[\.\-]\d+)*)',  # статья 123, статьи 123-456
        r'ст\. (\d+(?:[\.\-]\d+)*)',  # ст. 123
        r'пункт (\d+)',  # пункт 123 (for amendments to specific points)
    ]

    # Patterns for matching action types
    ACTION_PATTERNS = {
        'addition': [
            r'Дополнить.*стать(?:е|ей|ю|ей) \d+',
            r'Признать.*утратившим силу.*дополнить',
        ],
        'modification': [
            r'В стать(?:е|и|ю|ей) \d+.*(?:заменить|изложить)',
            r'Признать.*утратившим силу.*(?:абзац|пункт)',
        ],
        'repeal': [
            r'Признать.*утратившим силу.*стать(?:я|ю|и)',
            r'Исключить.*стать(?:я|ю|и)',
        ],
    }

    def __init__(self):
        """Initialize the amendment parser."""
        # Compile regex patterns for performance
        self.article_regex = re.compile(
            '|'.join(self.ARTICLE_PATTERNS),
            re.IGNORECASE | re.UNICODE
        )

    def parse_amendment(
        self,
        eo_number: str,
        title: str,
        text: str,
        effective_date: Optional[datetime] = None,
    ) -> ParsedAmendment:
        """
        Parse an amendment document.

        Args:
            eo_number: Amendment document number
            title: Amendment title
            text: Full amendment text
            effective_date: When amendment takes effect

        Returns:
            ParsedAmendment with extracted information
        """
        # Identify target code
        target = self._identify_target_code(title, text)

        # Extract article references
        articles_affected = self._extract_articles(title, text)

        # Determine action type
        action_type = self._determine_action_type(title, text)

        # Create parsed amendment
        return ParsedAmendment(
            eo_number=eo_number,
            title=title,
            code_id=target.code_id,
            code_name=target.code_name,
            action_type=action_type,
            effective_date=effective_date,
            raw_text=text,
        )

    def _identify_target_code(self, title: str, text: str) -> AmendmentTarget:
        """
        Identify which code is being amended.

        Args:
            title: Amendment title
            text: Amendment text

        Returns:
            AmendmentTarget with code information
        """
        combined = f"{title} {text}".lower()

        for code_id, patterns in CODE_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in combined:
                    # Get the full code name
                    code_name = patterns[0]  # First pattern is usually the full name
                    return AmendmentTarget(
                        code_id=code_id,
                        code_name=code_name,
                        articles_affected=[],
                        is_full_code=False,
                    )

        # Default: unknown code
        logger.warning(f"Could not identify target code in: {title[:100]}")
        return AmendmentTarget(
            code_id="UNKNOWN",
            code_name="Неизвестный кодекс",
            articles_affected=[],
            is_full_code=False,
        )

    def _extract_articles(self, title: str, text: str) -> List[str]:
        """
        Extract article numbers affected by amendment.

        Args:
            title: Amendment title
            text: Amendment text

        Returns:
            List of article numbers as strings
        """
        combined = f"{title} {text}"

        # Find all article references
        matches = self.article_regex.findall(combined)

        # Deduplicate and clean
        articles = list(set(matches))

        logger.debug(f"Found {len(articles)} article references: {articles}")
        return articles

    def _determine_action_type(self, title: str, text: str) -> str:
        """
        Determine the type of amendment action.

        Args:
            title: Amendment title
            text: Amendment text

        Returns:
            Action type: 'addition', 'modification', 'repeal', or 'mixed'
        """
        combined = f"{title} {text}".lower()

        actions_found = []

        for action_type, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    actions_found.append(action_type)
                    break

        if len(actions_found) == 0:
            # Default to modification if no clear pattern found
            return 'modification'
        elif len(actions_found) == 1:
            return actions_found[0]
        else:
            return 'mixed'

    def parse_change_details(
        self,
        amendment: ParsedAmendment,
        full_text: str,
    ) -> List[AmendmentChange]:
        """
        Parse detailed changes from amendment text.

        This attempts to extract old_text -> new_text mappings
        from the amendment language.

        Args:
            amendment: Previously parsed amendment
            full_text: Full amendment text

        Returns:
            List of AmendmentChange objects with details
        """
        changes = []
        text = full_text.lower()

        # Pattern: "слово X заменить словом Y"
        replacement_pattern = r'(?:слово|фразу|абзац|пункт)\s+["«]([^"»]+)["»]\s+заменить\s+["«]([^"»]+)["»]'
        for match in re.finditer(replacement_pattern, text, re.IGNORECASE):
            changes.append(AmendmentChange(
                action_type='modification',
                old_text=match.group(1),
                new_text=match.group(2),
                context=match.group(0),
            ))

        # Pattern: "дополнить статьей X: текст"
        addition_pattern = r'дополнить\s+стать(?:е|ей)\s+(\d+).*?:\s*([^.\n]+)'
        for match in re.finditer(addition_pattern, text, re.IGNORECASE):
            changes.append(AmendmentChange(
                action_type='addition',
                article_number=match.group(1),
                new_text=match.group(2),
                context=match.group(0),
            ))

        logger.debug(f"Parsed {len(changes)} detailed changes")
        return changes


def parse_amendment_from_db(
    eo_number: str,
    title: str,
    full_text: str,
    document_date: Optional[datetime] = None,
) -> ParsedAmendment:
    """
    Convenience function to parse an amendment from database fields.

    Args:
        eo_number: Amendment document number
        title: Amendment title
        full_text: Full amendment text
        document_date: Document publication date

    Returns:
        ParsedAmendment object
    """
    parser = AmendmentParser()
    return parser.parse_amendment(
        eo_number=eo_number,
        title=title,
        text=full_text,
        effective_date=document_date,
    )


# Convenience function for batch processing
def parse_amendments_batch(
    amendments: List[Dict[str, Any]],
) -> List[ParsedAmendment]:
    """
    Parse multiple amendments in batch.

    Args:
        amendments: List of amendment dictionaries with keys:
                   - eo_number
                   - title
                   - full_text
                   - document_date (optional)

    Returns:
        List of ParsedAmendment objects
    """
    parser = AmendmentParser()
    results = []

    for amendment in amendments:
        try:
            parsed = parser.parse_amendment(
                eo_number=amendment.get('eo_number', ''),
                title=amendment.get('title', ''),
                text=amendment.get('full_text', ''),
                effective_date=amendment.get('document_date'),
            )
            results.append(parsed)
        except Exception as e:
            logger.error(f"Failed to parse amendment {amendment.get('eo_number')}: {e}")
            continue

    logger.info(f"Parsed {len(results)}/{len(amendments)} amendments successfully")
    return results
