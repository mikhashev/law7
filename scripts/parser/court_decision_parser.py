"""
Court decision parser for extracting article references.

This parser extracts legal article citations from Russian court decisions.
It identifies references to legal codes (ГК РФ, УК РФ, ТК РФ, etc.) and specific articles.

Based on research of Russian court decision citation patterns.

Example citations found in court decisions:
- "ст. 15 ГК РФ" (article 15 of Civil Code)
- "статья 123 Трудового кодекса Российской Федерации"
- "п. 2 ст. 15 ГК РФ" (point 2 of article 15 of Civil Code)
- "ч. 1 ст. 12 КоАП РФ" (part 1 of article 12 of Administrative Code)
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Code identifier mappings (Russian names to standardized codes)
CODE_MAPPINGS = {
    # Full names -> codes
    "гражданский кодекс российской федерации": "GK_RF",
    "гражданский кодекс": "GK_RF",
    "гк рф": "GK_RF",
    "гк российской федерации": "GK_RF",

    "уголовный кодекс российской федерации": "UK_RF",
    "уголовный кодекс": "UK_RF",
    "ук рф": "UK_RF",
    "ук российской федерации": "UK_RF",

    "трудовой кодекс российской федерации": "TK_RF",
    "трудовой кодекс": "TK_RF",
    "тк рф": "TK_RF",
    "тк российской федерации": "TK_RF",

    "налоговый кодекс российской федерации": "NK_RF",
    "налоговый кодекс": "NK_RF",
    "нк рф": "NK_RF",
    "нк российской федерации": "NK_RF",

    "кодекс об административных правонарушениях": "KoAP_RF",
    "коап рф": "KoAP_RF",
    "кодекс российской федерации об административных правонарушениях": "KoAP_RF",

    "семейный кодекс российской федерации": "SK_RF",
    "семейный кодекс": "SK_RF",
    "ск рф": "SK_RF",

    "жилищный кодекс российской федерации": "ZhK_RF",
    "жилищный кодекс": "ZhK_RF",
    "жк рф": "ZhK_RF",

    "земельный кодекс российской федерации": "ZK_RF",
    "земельный кодекс": "ZK_RF",
    "зк рф": "ZK_RF",

    "арбитражный процессуальный кодекс российской федерации": "APK_RF",
    "арбитражный процессуальный кодекс": "APK_RF",
    "апк рф": "APK_RF",

    "гражданский процессуальный кодекс российской федерации": "GPK_RF",
    "гражданский процессуальный кодекс": "GPK_RF",
    "гпк рф": "GPK_RF",

    "уголовно-процессуальный кодекс российской федерации": "UPK_RF",
    "уголовно-процессуальный кодекс": "UPK_RF",
    "упк рф": "UPK_RF",

    "бюджетный кодекс российской федерации": "BK_RF",
    "бюджетный кодекс": "BK_RF",
    "бк рф": "BK_RF",

    "градостроительный кодекс российской федерации": "GRK_RF",
    "градостроительный кодекс": "GRK_RF",
    "грк рф": "GRK_RF",

    "уголовно-исполнительный кодекс российской федерации": "UIK_RF",
    "уголовно-исполнительный кодекс": "UIK_RF",
    "уик рф": "UIK_RF",

    "воздушный кодекс российской федерации": "VZK_RF",
    "воздушный кодекс": "VZK_RF",
    "вк рф": "VZK_RF",

    "водный кодекс российской федерации": "VDK_RF",
    "водный кодекс": "VDK_RF",
    "вк рф": "VDK_RF",

    "лесной кодекс российской федерации": "LK_RF",
    "лесной кодекс": "LK_RF",
    "лк рф": "LK_RF",

    "кодекс административного судопроизводства российской федерации": "KAS_RF",
    "кодекс административного судопроизводства": "KAS_RF",
    "кас рф": "KAS_RF",

    "конституция российской федерации": "KONST_RF",
    "конституция рф": "KONST_RF",
    "конституция": "KONST_RF",
}


class CourtDecisionParser:
    """
    Parser for extracting article references from Russian court decisions.

    This parser identifies citations to legal codes and articles within court
    decision text, enabling links between court decisions and the articles
    they interpret or apply.

    Attributes:
        country_id: ISO 3166-1 alpha-3 code ("RUS")
        country_name: Full country name ("Russia")
    """

    # Country identification
    country_id = "RUS"
    country_name = "Russia"

    # Article citation patterns
    # Pattern 1: "ст. 15 ГК РФ" or "статья 15 ГК РФ"
    # Pattern 2: "п. 2 ст. 15 ГК РФ" (point/paragraph reference)
    # Pattern 3: "ч. 1 ст. 12 КоАП РФ" (part reference)
    # Pattern 4: "ст. 105.1 ГК РФ" (decimal article numbers)

    # Regex patterns for article citations
    PATTERNS = [
        # Full citation: "ст. 15 ГК РФ" or "статья 15 Гражданского кодекса"
        re.compile(
            r'(?:ст\.?\s*|статья\s+)(\d+(?:\.\d+)?)\s+([А-ЯЁA-Zа-яёa-z][А-ЯЁA-Zа-яёa-z\s\.]*(?:РФ|России)?)',
            re.IGNORECASE
        ),
        # Point/paragraph reference: "п. 2 ст. 15 ГК РФ"
        re.compile(
            r'(?:п\.?\s*|пункт\s+)(\d+(?:\.\d+)?)\s*(?:ст\.?\s*|статья\s+)(\d+(?:\.\d+)?)\s+([А-ЯЁA-Zа-яёa-z][А-ЯЁA-Zа-яёa-z\s\.]*(?:РФ|России)?)',
            re.IGNORECASE
        ),
        # Part reference: "ч. 1 ст. 12 КоАП РФ"
        re.compile(
            r'(?:ч\.?\s*|часть\s+)(\d+(?:\.\d+)?)\s*(?:ст\.?\s*|статья\s+)(\d+(?:\.\d+)?)\s+([А-ЯЁA-Zа-яёa-z][А-ЯЁA-Zа-яёa-z\s\.]*(?:РФ|России)?)',
            re.IGNORECASE
        ),
        # Short code pattern: "ст. 15 ГК"
        re.compile(
            r'(?:ст\.?\s*|статья\s+)(\d+(?:\.\d+)?)\s+([А-ЯЁA-Z]{2,6})\s?',
            re.IGNORECASE
        ),
    ]

    def __init__(self):
        """Initialize the court decision parser."""
        logger.info("CourtDecisionParser initialized")

    def extract_article_references(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract article references from court decision text.

        Args:
            text: Full text of the court decision

        Returns:
            List of article reference dictionaries with keys:
                - code_id: Standardized code identifier (e.g., "GK_RF")
                - article_number: Article number (e.g., "123", "124.1")
                - reference_context: Excerpt showing the citation context
                - reference_type: Type of reference ("cited", "interpreted", "applied")
                - position_in_text: Character position where reference appears

        Example:
            >>> parser = CourtDecisionParser()
            >>> text = "Суд применил ст. 15 ГК РФ при рассмотрении дела."
            >>> refs = parser.extract_article_references(text)
            >>> print(refs[0]['code_id'])  # "GK_RF"
            >>> print(refs[0]['article_number'])  # "15"
        """
        if not text:
            return []

        references = []
        seen_references = set()  # Avoid duplicates

        for pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                try:
                    ref = self._parse_match(match, text)
                    if ref:
                        # Create unique key for deduplication
                        ref_key = (ref['code_id'], ref['article_number'])
                        if ref_key not in seen_references:
                            seen_references.add(ref_key)
                            references.append(ref)
                except Exception as e:
                    logger.warning(f"Failed to parse article reference: {e}")
                    continue

        logger.info(f"Extracted {len(references)} article references")
        return references

    def _parse_match(
        self,
        match: re.Match,
        text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a regex match into an article reference.

        Args:
            match: Regex match object
            text: Full text for context extraction

        Returns:
            Article reference dictionary or None if parsing fails
        """
        groups = match.groups()

        # Determine article number and code name based on pattern
        if len(groups) >= 2 and groups[0] and groups[1]:
            # Check if this is a point/part reference (3 groups)
            if len(groups) == 3 and groups[2]:
                # Point/part reference: "п. 2 ст. 15 ГК РФ"
                article_number = groups[1]  # Second group is article
                code_name = groups[2]  # Third group is code
            else:
                # Simple reference: "ст. 15 ГК РФ"
                article_number = groups[0]
                code_name = groups[1]

            # Normalize code name to code_id
            code_id = self._normalize_code_name(code_name)
            if not code_id:
                return None

            # Get reference context (surrounding text)
            start, end = match.span()
            context_start = max(0, start - 100)
            context_end = min(len(text), end + 100)
            context = text[context_start:context_end].strip()

            # Determine reference type from context
            reference_type = self._classify_reference_type(context)

            return {
                'code_id': code_id,
                'article_number': article_number,
                'reference_context': context,
                'reference_type': reference_type,
                'position_in_text': start,
            }

        return None

    def _normalize_code_name(self, code_name: str) -> Optional[str]:
        """
        Normalize a code name to the standardized code_id.

        Args:
            code_name: Raw code name from text (e.g., "ГК РФ", "Гражданского кодекса")

        Returns:
            Standardized code_id (e.g., "GK_RF") or None if not recognized

        Example:
            >>> parser = CourtDecisionParser()
            >>> parser._normalize_code_name("ГК РФ")  # "GK_RF"
            >>> parser._normalize_code_name("Гражданского кодекса")  # "GK_RF"
        """
        if not code_name:
            return None

        # Normalize: lowercase, strip extra whitespace
        normalized = code_name.lower().strip()

        # Direct match
        if normalized in CODE_MAPPINGS:
            return CODE_MAPPINGS[normalized]

        # Fuzzy match: check if normalized string contains a known code
        for known_name, code_id in CODE_MAPPINGS.items():
            if known_name in normalized or normalized in known_name:
                return code_id

        # Try to parse short code (e.g., "ГК" -> "GK_RF")
        short_match = re.match(r'^([А-ЯЁA-Z]{2,6})$', code_name.strip().upper())
        if short_match:
            short_code = short_match.group(1)
            # Map short codes
            short_mappings = {
                'ГК': 'GK_RF',
                'УК': 'UK_RF',
                'ТК': 'TK_RF',
                'НК': 'NK_RF',
                'КоАП': 'KoAP_RF',
                'СК': 'SK_RF',
                'ЖК': 'ZhK_RF',
                'ЗК': 'ZK_RF',
                'АПК': 'APK_RF',
                'ГПК': 'GPK_RF',
                'УПК': 'UPK_RF',
                'БК': 'BK_RF',
                'ГрК': 'GRK_RF',
                'УИК': 'UIK_RF',
                'ВК': 'VZK_RF',
                'ЛК': 'LK_RF',
                'КАС': 'KAS_RF',
            }
            return short_mappings.get(short_code)

        logger.debug(f"Could not normalize code name: {code_name}")
        return None

    def _classify_reference_type(self, context: str) -> str:
        """
        Classify the type of article reference based on context.

        Args:
            context: Text surrounding the citation

        Returns:
            Reference type: "cited", "interpreted", "applied", "distinguished"

        Example:
            >>> parser = CourtDecisionParser()
            >>> parser._classify_reference_type("Суд применил ст. 15 ГК РФ")
            # Returns: "applied"
        """
        context_lower = context.lower()

        # Classification keywords (Russian)
        applied_keywords = ['применил', 'применить', 'применяя', 'согласно']
        interpreted_keywords = ['разъяснил', 'толкование', 'толкует', 'суд считает']
        distinguished_keywords = ['отличается', 'не применяется', 'иное']
        cited_keywords = ['ссылается', 'указал', 'согласно', 'в соответствии']

        for keyword in applied_keywords:
            if keyword in context_lower:
                return 'applied'

        for keyword in interpreted_keywords:
            if keyword in context_lower:
                return 'interpreted'

        for keyword in distinguished_keywords:
            if keyword in context_lower:
                return 'distinguished'

        # Default to cited
        return 'cited'

    def extract_summary(
        self,
        full_text: str,
        max_length: int = 500,
    ) -> str:
        """
        Extract a summary from court decision text.

        Args:
            full_text: Full text of the decision
            max_length: Maximum length of summary

        Returns:
            Summary text (first paragraph or truncated text)

        Example:
            >>> parser = CourtDecisionParser()
            >>> text = "Резолютивная часть:\n\nСуд постановил..."
            >>> summary = parser.extract_summary(text)
        """
        if not full_text:
            return ""

        # Split into paragraphs
        paragraphs = full_text.split('\n\n')

        # Find the first substantial paragraph (after headers)
        for para in paragraphs:
            para = para.strip()
            if len(para) > 50:  # Skip headers/short lines
                # Truncate to max_length
                if len(para) > max_length:
                    para = para[:max_length].rsplit(' ', 1)[0] + '...'
                return para

        # Fallback: truncate full text
        if len(full_text) > max_length:
            return full_text[:max_length].rsplit(' ', 1)[0] + '...'
        return full_text

    def parse_court_decision(
        self,
        decision_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Parse a court decision and extract all relevant information.

        Args:
            decision_data: Raw decision data with at least 'full_text' field

        Returns:
            Parsed decision with:
                - article_references: List of extracted article references
                - summary: Extracted summary
                - text_hash: Hash for change detection

        Example:
            >>> parser = CourtDecisionParser()
            >>> data = {'full_text': 'Суд применил ст. 15 ГК РФ...'}
            >>> parsed = parser.parse_court_decision(data)
            >>> print(parsed['article_references'][0]['code_id'])
        """
        full_text = decision_data.get('full_text') or decision_data.get('decision_text', '')

        # Extract article references
        article_references = self.extract_article_references(full_text)

        # Extract summary
        summary = self.extract_summary(full_text)

        # Generate text hash
        import hashlib
        text_hash = hashlib.sha256(full_text.encode('utf-8')).hexdigest()

        return {
            'article_references': article_references,
            'summary': summary,
            'text_hash': text_hash,
        }


def parse_court_decision(decision_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to parse a court decision.

    Args:
        decision_data: Raw decision data

    Returns:
        Parsed decision with article references, summary, and text_hash

    Example:
        >>> from parser.court_decision_parser import parse_court_decision
        >>> data = {'full_text': 'Суд применил ст. 15 ГК РФ...'}
        >>> parsed = parse_court_decision(data)
    """
    parser = CourtDecisionParser()
    return parser.parse_court_decision(decision_data)
