"""
Court decision parser for extracting article references from Russian court decisions.

This is the Russia-specific parser for court decisions from Russian courts.
"""
from parser.court_decision_parser import (
    CourtDecisionParser,
    CODE_MAPPINGS,
    parse_court_decision,
)

__all__ = [
    "CourtDecisionParser",
    "CODE_MAPPINGS",
    "parse_court_decision",
]
