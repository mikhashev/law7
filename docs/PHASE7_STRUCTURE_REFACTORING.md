# Phase 7: Project Structure Refactoring

**Duration:** Months 3-4 (parallel with Phase 3)
**Priority:** HIGH
**Status:** Not Started

**Informed by:** [Phase 0: P2P Research](./PHASE0_P2P_RESEARCH.md)

---

## Overview

Restructure codebase to support pluggable country modules, enabling future multi-country expansion. This refactoring is informed by P2P research to ensure architecture can support both centralized and decentralized modes.

---

## 7.1 Pluggable Country Module Architecture

**Goal:** Restructure codebase to support country-agnostic core with pluggable country-specific modules

### Current Structure

```
scripts/
├── crawler/        # pravo.gov.ru API (Russia-specific)
├── parser/         # Russian legal document parser
├── consolidation/  # Russian code consolidation
├── sync/           # Russian data sync
└── import/         # Russian legal codes
```

### Target Structure

```
scripts/
├── core/               # Country-independent (existing, expand)
│   ├── config.py
│   ├── db.py
│   ├── batch_saver.py
│   └── ...
│
├── country_modules/    # Country-specific modules (NEW)
│   ├── base/           # Abstract base classes
│   │   ├── scraper.py          # BaseScraper interface
│   │   ├── parser.py           # BaseParser interface
│   │   ├── consolidator.py     # BaseConsolidator interface
│   │   └── schema.py           # Base schema definitions
│   │
│   ├── russia/         # Russian Federation (refactor existing)
│   │   ├── scrapers/
│   │   │   ├── pravo_api_client.py
│   │   │   ├── regional_scraper.py
│   │   │   └── court_scraper.py
│   │   ├── parsers/
│   │   │   ├── html_parser.py
│   │   │   ├── court_parser.py
│   │   │   └── amendment_parser.py
│   │   ├── consolidation/
│   │   │   ├── consolidate.py
│   │   │   ├── amendment_parser.py
│   │   │   └── diff_engine.py
│   │   ├── schemas/
│   │   │   └── russia_schema.sql
│   │   └── __init__.py
│   │
│   └── germany/       # Germany (future)
│       └── ...
│
├── legal_systems/     # Legal system adapters (NEW)
│   ├── civil_law/     # Code-based systems (Russia, Germany, France)
│   │   ├── schema.py  # Common schema for civil law
│   │   └── parser.py  # Common parsing patterns
│   │
│   └── common_law/    # Case law systems (UK, USA, Canada)
│       ├── schema.py  # Common schema for common law
│       └── parser.py  # Case citation parsing
│
└── indexer/           # Country-agnostic (unchanged)
    ├── embeddings.py
    ├── qdrant_indexer.py
    └── postgres_indexer.py
```

### Files to Create

- `scripts/country_modules/base/scraper.py` - Abstract base class for scrapers
- `scripts/country_modules/base/parser.py` - Abstract base class for parsers
- `scripts/country_modules/base/consolidator.py` - Abstract base class for consolidation
- `scripts/legal_systems/civil_law/schema.py` - Civil law common schema
- `scripts/legal_systems/common_law/schema.py` - Common law common schema

### Files to Refactor

- `scripts/crawler/pravo_api_client.py` → `scripts/country_modules/russia/scrapers/pravo_api_client.py`
- `scripts/parser/html_parser.py` → `scripts/country_modules/russia/parsers/html_parser.py`
- `scripts/consolidation/consolidate.py` → `scripts/country_modules/russia/consolidation/consolidate.py`

---

## 7.2 Country Registry and Configuration

**Priority:** HIGH - Enables multi-country support

### Create Country Registry

```python
# scripts/country_modules/registry.py
from typing import Dict, Type
from country_modules.base.scraper import BaseScraper
from country_modules.base.parser import BaseParser

class CountryModule:
    """Country-specific module configuration"""

    def __init__(
        self,
        country_id: str,        # ISO 3166-1 alpha-3 (e.g., "RUS", "DEU")
        country_name: str,
        legal_system: str,      # "civil_law", "common_law", "mixed"
        scraper_class: Type[BaseScraper],
        parser_class: Type[BaseParser],
        data_sources: Dict[str, str],
        jurisdiction_levels: list,
    ):
        ...

# Country registry
COUNTRIES: Dict[str, CountryModule] = {
    "RUS": CountryModule(
        country_id="RUS",
        country_name="Russia",
        legal_system="civil_law",
        scraper_class=RussiaPravoScraper,
        parser_class=RussiaHtmlParser,
        data_sources={
            "federal": "http://pravo.gov.ru",
            "supreme_court": "https://vsrf.ru",
            "constitutional_court": "http://www.ksrf.ru",
        },
        jurisdiction_levels=["federal", "regional", "municipal"],
    ),
    # Future countries:
    # "DEU": CountryModule(...),
    # "FRA": CountryModule(...),
}

def get_country_module(country_id: str) -> CountryModule:
    """Get country module by ID"""
    return COUNTRIES.get(country_id)
```

### Files to Create

- `scripts/country_modules/registry.py`
- `scripts/country_modules/__init__.py`

---

## 7.3 Database Schema for Multi-Country

**Priority:** HIGH - Support multiple countries in single database

### Schema Updates

```sql
-- Add country_id to existing tables
ALTER TABLE documents ADD COLUMN country_id VARCHAR(3) NOT NULL DEFAULT 'RUS';
ALTER TABLE documents ADD CONSTRAINT fk_country
    FOREIGN KEY (country_id) REFERENCES countries(id);

ALTER TABLE documents ADD COLUMN jurisdiction_level VARCHAR(20);
    -- 'federal', 'regional', 'municipal', 'state', etc.

ALTER TABLE documents ADD COLUMN jurisdiction_id VARCHAR(100);
    -- For federal systems: region code, state code, etc.

-- Update countries table
CREATE TABLE countries (
    id VARCHAR(3) PRIMARY KEY,      -- ISO 3166-1 alpha-3
    name_en VARCHAR(100),
    name_native VARCHAR(100),
    legal_system_type VARCHAR(50),  -- 'civil_law', 'common_law', 'mixed'
    federal_structure BOOLEAN,
    official_languages VARCHAR(100)[],
    data_sources JSONB,             -- Country-specific source URLs
    scraper_config JSONB,           -- Scraper settings
    parser_config JSONB,            -- Parser settings
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for country-specific queries
CREATE INDEX idx_documents_country ON documents(country_id, jurisdiction_level);
```

### Files to Modify

- `docker/postgres/init.sql` (add countries table, country_id columns)

---

## 7.4 MCP Server Country Parameter

**Priority:** MEDIUM - Support multi-country queries

### Update MCP Tools

```typescript
// src/tools/query-laws.ts
export const queryLawsTool = {
  name: "query-laws",
  description: "Search legal documents by country",
  inputSchema: {
    country?: "string",        -- NEW: Country code (default: "RUS")
    query: "string",
    filters?: "SearchFilters",
    use_hybrid?: "boolean"
  }
};

// src/tools/list-countries.ts
export const listCountriesTool = {
  name: "list-countries",
  description: "List supported countries",
  inputSchema: {}
  // Returns: ["RUS", "DEU", ...] with metadata
};
```

### Files to Modify

- `src/tools/query-laws.ts` (add country parameter)
- `src/tools/list-countries.ts` (return from registry)
- `src/db/postgres.ts` (add country filtering)

---

## 7.5 Migration Path for Russia Module

**Priority:** HIGH - Existing functionality must continue working

### Migration Steps

1. **Create new structure** without touching existing code
2. **Move Russia module** to `country_modules/russia/`
3. **Create shims** for backward compatibility:
   ```python
   # scripts/crawler/pravo_api_client.py (shim)
   from country_modules.russia.scrapers.pravo_api_client import PravoApiClient
   # Re-export for backward compatibility
   ```
4. **Update imports** gradually
5. **Remove shims** after all imports updated

### Backward Compatibility

- All existing scripts continue to work
- Gradual migration via shims
- No breaking changes to MCP tools
- Database migration uses default `country_id='RUS'`

---

## Deliverables

- Refactored codebase with country modules
- Country registry and configuration
- Multi-country database schema
- MCP server country parameter support
- Backward-compatible migration completed

---

## Related Phases

- **Informed by:** [Phase 0: P2P Research](./PHASE0_P2P_RESEARCH.md)
- **Parallel with:** [Phase 3](./PHASE3_OCR.md)
- **Enables:** [Phase 4](./PHASE4_REGIONAL.md) (country architecture foundation)

---

## Timeline

**Month 3:** Create base classes, refactor core modules
**Month 4:** Move Russia module, create shims, test migration

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** Phase 0 (P2P research guidance)
**Blocking:** Phase 4 (regional), future country expansion
