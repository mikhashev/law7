"""
Backward compatibility shim for AmendmentParser.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.consolidation.amendment_parser.

Deprecated: Please import from country_modules.russia.consolidation.amendment_parser instead.
"""
# Re-export everything from the new location
from country_modules.russia.consolidation.amendment_parser import (
    AmendmentParser,
    ParsedAmendment,
    AmendmentTarget,
    AmendmentChange,
    parse_amendment_from_db,
    parse_amendments_batch,
    CODE_PATTERNS,
)

__all__ = [
    "AmendmentParser",
    "ParsedAmendment",
    "AmendmentTarget",
    "AmendmentChange",
    "parse_amendment_from_db",
    "parse_amendments_batch",
    "CODE_PATTERNS",
]