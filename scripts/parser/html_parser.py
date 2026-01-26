"""
Backward compatibility shim for PravoContentParser.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.parsers.html_parser.

Deprecated: Please import from country_modules.russia.parsers.html_parser instead.
"""
# Re-export everything from the new location
from country_modules.russia.parsers.html_parser import (
    PravoContentParser,
    parse_pravo_document,
)

__all__ = [
    "PravoContentParser",
    "parse_pravo_document",
]