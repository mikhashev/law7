"""
Backward compatibility shim for PravoApiClient.

This file provides backward compatibility for imports from the old location.
The actual implementation is now at country_modules.russia.scrapers.pravo_api_client.

Deprecated: Please import from country_modules.russia.scrapers.pravo_api_client instead.
"""
# Re-export everything from the new location
from country_modules.russia.scrapers.pravo_api_client import (
    PravoApiClient,
    fetch_documents_for_date,
)

__all__ = [
    "PravoApiClient",
    "fetch_documents_for_date",
]
