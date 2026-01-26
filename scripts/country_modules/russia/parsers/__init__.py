"""
Russia-specific parsers for legal documents.

This module contains parsers for:
- HTML document parsing from pravo.gov.ru
- PDF document parsing with OCR
- Amendment document parsing
- Court decision parsing (future - Phase 7C)
"""
from .html_parser import PravoContentParser, parse_pravo_document
from .html_scraper import AmendmentHTMLScraper, scrape_amendment

__all__ = [
    "PravoContentParser",
    "parse_pravo_document",
    "AmendmentHTMLScraper",
    "scrape_amendment",
]
