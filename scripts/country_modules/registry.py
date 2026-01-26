"""
Country module registry.

This module provides a registry of all available country modules and their
configurations. Each country module defines scrapers, parsers, and sync services
specific to that country's legal system and data sources.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class CountryModule:
    """
    Country-specific module configuration.

    This dataclass stores the configuration for a country's legal document
    processing pipeline, including scraper, parser, consolidation, and sync
    implementations.
    """

    country_id: str  # ISO 3166-1 alpha-3 (e.g., "RUS", "DEU", "USA")
    country_name: str  # Full country name (e.g., "Russia", "Germany")
    country_code: str  # ISO 3166-1 alpha-2 (e.g., "RU", "DE", "US")
    legal_system: str  # "civil_law", "common_law", "mixed"
    scraper_class_path: str  # Python import path to scraper class
    parser_class_path: str  # Python import path to parser class
    consolidation_path: Optional[str] = None  # Path to consolidation module (optional)
    sync_path: Optional[str] = None  # Path to sync module (optional)
    data_sources: Dict[str, str] = None  # Source URLs keyed by type
    jurisdiction_levels: List[str] = None  # ["federal", "regional", "municipal"]
    is_active: bool = True

    def __post_init__(self):
        if self.data_sources is None:
            self.data_sources = {}
        if self.jurisdiction_levels is None:
            self.jurisdiction_levels = []


# Country registry with all configured countries
COUNTRIES: Dict[str, CountryModule] = {
    "RUS": CountryModule(
        country_id="RUS",
        country_name="Russia",
        country_code="RU",
        legal_system="civil_law",
        scraper_class_path="country_modules.russia.scrapers.pravo_api_client.PravoApiClient",
        parser_class_path="country_modules.russia.parsers.html_parser.PravoContentParser",
        consolidation_path="country_modules.russia.consolidation",
        sync_path="country_modules.russia.sync",
        data_sources={
            "federal": "http://pravo.gov.ru",
            "supreme_court": "https://vsrf.ru",
            "constitutional_court": "http://www.ksrf.ru",
            "minfin": "https://minfin.gov.ru",
            "rostrud": "https://rostrud.gov.ru",
        },
        jurisdiction_levels=["federal", "regional", "municipal"],
        is_active=True,
    ),
    # Future countries (Phase 4):
    # "DEU": CountryModule(
    #     country_id="DEU",
    #     country_name="Germany",
    #     country_code="DE",
    #     legal_system="civil_law",
    #     ...
    # ),
}


def get_country_module(country_id: str) -> Optional[CountryModule]:
    """
    Get country module by ID.

    Args:
        country_id: ISO 3166-1 alpha-3 code (e.g., "RUS", "DEU", "USA")
                  Case-insensitive.

    Returns:
        CountryModule if found, None otherwise

    Examples:
        >>> module = get_country_module("RUS")
        >>> module.country_name
        'Russia'
        >>> module = get_country_module("rus")  # Case-insensitive
        >>> module.country_name
        'Russia'
    """
    if not country_id:
        return None
    return COUNTRIES.get(country_id.upper())


def get_country_module_by_code(country_code: str) -> Optional[CountryModule]:
    """
    Get country module by ISO alpha-2 code.

    Args:
        country_code: ISO 3166-1 alpha-2 code (e.g., "RU", "DE", "US")
                     Case-insensitive.

    Returns:
        CountryModule if found, None otherwise
    """
    if not country_code:
        return None
    country_code_upper = country_code.upper()
    for module in COUNTRIES.values():
        if module.country_code == country_code_upper:
            return module
    return None


def list_available_countries() -> List[str]:
    """
    Get list of available country IDs.

    Returns:
        List of ISO 3166-1 alpha-3 country codes (e.g., ["RUS"])

    Examples:
        >>> list_available_countries()
        ['RUS']
    """
    return list(COUNTRIES.keys())


def list_active_countries() -> List[str]:
    """
    Get list of active country IDs.

    Returns:
        List of ISO 3166-1 alpha-3 country codes for active countries
    """
    return [
        country_id
        for country_id, module in COUNTRIES.items()
        if module.is_active
    ]


def get_country_config(country_id: str) -> Optional[Dict[str, any]]:
    """
    Get country configuration as dict.

    Args:
        country_id: ISO 3166-1 alpha-3 code (e.g., "RUS", "DEU", "USA")

    Returns:
        Dict with country configuration or None if not found

    Examples:
        >>> config = get_country_config("RUS")
        >>> config['country_name']
        'Russia'
        >>> config['legal_system']
        'civil_law'
    """
    module = get_country_module(country_id)
    if not module:
        return None
    return {
        'country_id': module.country_id,
        'country_code': module.country_code,
        'country_name': module.country_name,
        'legal_system': module.legal_system,
        'data_sources': module.data_sources,
        'jurisdiction_levels': module.jurisdiction_levels,
        'is_active': module.is_active,
    }


def register_country(module: CountryModule) -> None:
    """
    Register a new country module.

    Args:
        module: CountryModule configuration

    Raises:
        ValueError: If country_id already exists

    Examples:
        >>> from country_modules.registry import CountryModule, register_country
        >>> module = CountryModule(
        ...     country_id="DEU",
        ...     country_name="Germany",
        ...     country_code="DE",
        ...     legal_system="civil_law",
        ...     scraper_class_path="...",
        ...     parser_class_path="...",
        ...     data_sources={},
        ...     jurisdiction_levels=["federal", "state"],
        ... )
        >>> register_country(module)
    """
    country_id = module.country_id.upper()
    if country_id in COUNTRIES:
        raise ValueError(f"Country {country_id} already registered")
    COUNTRIES[country_id] = module
