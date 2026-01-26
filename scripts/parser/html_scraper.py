"""
Backward compatibility shim for AmendmentHTMLScraper.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.parsers.html_scraper.

Deprecated: Please import from country_modules.russia.parsers.html_scraper instead.
"""
# Re-export everything from the new location
from country_modules.russia.parsers.html_scraper import (
    AmendmentHTMLScraper,
    scrape_amendment,
)

__all__ = [
    "AmendmentHTMLScraper",
    "scrape_amendment",
]