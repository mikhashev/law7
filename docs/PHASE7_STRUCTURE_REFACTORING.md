# Phase 7: Project Structure Refactoring

**Duration:** 8 weeks (Weeks 1-8)
**Priority:** HIGH
**Status:** Ready to start

**IMPORTANT:** This phase now comes FIRST, before Phase 0. We will define the DocumentSync interface that Phase 0 will implement.

---

## Overview

Restructure codebase to support pluggable country modules, enabling future multi-country expansion. This refactoring defines clear interfaces that Phase 0 will implement with P2P technologies.

### Why Phase 7 First?

**The Problem We're Solving:**

Current user experience:
- Every Law7 user must install Docker, start containers, parse 157K documents themselves
- Massive duplication of effort across users
- Future scale problem: 200+ countries × thousands of daily updates

**The Solution:**
1. **Phase 7**: Define interfaces for multi-country + DocumentSync ABC
2. **Phase 0**: Implement DocumentSync with P2P technologies
3. **Phase 4**: Add new countries using Phase 7 structure + Phase 0 sync

---

## 7.1 New Directory Structure

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
├── core/                          # Country-independent (existing, expand)
│   ├── config.py
│   ├── db.py
│   ├── batch_saver.py
│   └── ...
│
├── country_modules/               # NEW: Country-specific modules
│   ├── base/                       # Abstract base classes
│   │   ├── __init__.py
│   │   ├── scraper.py              # BaseScraper ABC
│   │   ├── parser.py               # BaseParser ABC
│   │   ├── schema.py               # Base schema definitions
│   │   └── sync.py                 # DocumentSync ABC (NEW: for P2P)
│   │
│   ├── russia/                     # Refactor existing code
│   │   ├── __init__.py
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── pravo_api_client.py      # From scripts/crawler/
│   │   │   ├── regional_scraper.py     # Future
│   │   │   └── court_scraper.py        # Future
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── html_parser.py          # From scripts/parser/
│   │   │   ├── court_parser.py         # Future
│   │   │   └── amendment_parser.py     # From consolidation/
│   │   ├── consolidation/
│   │   │   ├── __init__.py
│   │   │   ├── consolidate.py          # From scripts/consolidation/
│   │   │   ├── amendment_parser.py
│   │   │   ├── diff_engine.py
│   │   │   └── version_manager.py
│   │   └── schemas/
│   │       └── russia_schema.sql       # Country-specific schema
│   │
│   ├── germany/                    # Future: First expansion country
│   │   └── ...
│   │
│   └── registry.py                 # Country module registry
│
├── sync/                          # NEW: Sync coordination
│   ├── __init__.py
│   ├── coordinator.py              # Sync orchestration
│   ├── manifest.py                 # Document manifest tracking
│   └── postgres_sync.py            # Current implementation (DocumentSync)
│
├── indexer/                       # Country-agnostic (unchanged)
│   ├── embeddings.py
│   ├── qdrant_indexer.py
│   └── postgres_indexer.py
│
└── [existing modules stay]
```

---

## 7.2 Base Classes

### 7.2.1 BaseScraper Interface

**File:** `scripts/country_modules/base/scraper.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import date

class DocumentManifest:
    """List of documents + their versions"""
    country_id: str
    documents: Dict[str, str]  # doc_id -> content_hash
    last_updated: str
    metadata: Dict[str, Any] = {}

class RawDocument:
    """Raw document from scraper"""
    doc_id: str
    url: str
    content: bytes
    content_type: str  # "text/html", "application/pdf"
    metadata: Dict[str, Any]

class BaseScraper(ABC):
    """Base class for country-specific scrapers"""

    @property
    @abstractmethod
    def country_id(self) -> str:
        """ISO 3166-1 alpha-3 code (e.g., 'RUS', 'DEU', 'USA')"""
        pass

    @property
    @abstractmethod
    def country_name(self) -> str:
        """Full country name (e.g., 'Russia', 'Germany')"""
        pass

    @property
    @abstractmethod
    def legal_system(self) -> str:
        """'civil_law', 'common_law', or 'mixed'"""
        pass

    @abstractmethod
    async def fetch_manifest(self, since: Optional[date] = None) -> DocumentManifest:
        """Get list of documents updated since date"""
        pass

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> RawDocument:
        """Fetch single document by ID"""
        pass

    @abstractmethod
    async def fetch_updates(self, since: date) -> List[RawDocument]:
        """Fetch all documents updated since date"""
        pass

    @abstractmethod
    async def verify_document(self, doc_id: str, content_hash: str) -> bool:
        """Verify document content matches hash"""
        pass
```

### 7.2.2 DocumentSync Interface (For P2P)

**File:** `scripts/country_modules/base/sync.py`

```python
from abc import ABC, abstractmethod
from typing import List, Callable, Dict, Any, Optional
from .scraper import DocumentManifest

class DocumentSync(ABC):
    """
    Abstract interface for document synchronization.

    This interface will be implemented by:
    1. PostgreSQLSync (current implementation, local-only) - Phase 7
    2. IPFSSync (IPFS-based P2P, Phase 0 PoC)
    3. DPCSync (D-PC Messenger-based, Phase 0 PoC)
    """

    @abstractmethod
    async def publish_manifest(self, manifest: DocumentManifest) -> None:
        """Publish document manifest to network"""
        pass

    @abstractmethod
    async def get_manifest(self, country_id: str) -> DocumentManifest:
        """Get current manifest for country"""
        pass

    @abstractmethod
    async def publish_document(self, country_id: str, doc_id: str,
                               content: bytes, metadata: Dict[str, Any]) -> str:
        """Publish document, return content hash"""
        pass

    @abstractmethod
    async def get_document(self, country_id: str, doc_id: str) -> bytes:
        """Get document content by ID"""
        pass

    @abstractmethod
    async def subscribe_to_updates(self, country_id: str,
                                   callback: Callable[[List[str]], None]) -> None:
        """Subscribe to document updates for country"""
        pass

    @abstractmethod
    async def get_country_list(self) -> List[str]:
        """Get list of available countries"""
        pass

    @abstractmethod
    async def get_country_config(self, country_id: str) -> Dict[str, Any]:
        """Get country configuration"""
        pass
```

---

## 7.3 PostgreSQLSync (Current Implementation)

**File:** `scripts/sync/postgres_sync.py`

```python
from country_modules.base.sync import DocumentSync
from country_modules.base.scraper import DocumentManifest
from typing import List, Callable, Dict, Any
from ..core.db import DatabaseClient

class PostgreSQLSync(DocumentSync):
    """Current implementation - local PostgreSQL only"""

    def __init__(self, db: DatabaseClient):
        self.db = db

    async def publish_manifest(self, manifest: DocumentManifest) -> None:
        """Store manifest in documents table"""
        # TODO: Implement manifest storage
        pass

    async def get_manifest(self, country_id: str) -> DocumentManifest:
        """Query documents table for country"""
        # TODO: Query and build manifest
        pass

    async def publish_document(self, country_id: str, doc_id: str,
                               content: bytes, metadata: Dict[str, Any]) -> str:
        """Store document in database"""
        # Use existing db.py methods
        content_hash = hashlib.sha256(content).hexdigest()
        # TODO: Store document
        return content_hash

    async def get_document(self, country_id: str, doc_id: str) -> bytes:
        """Retrieve document from database"""
        # Use existing db.py methods
        pass

    async def subscribe_to_updates(self, country_id: str,
                                   callback: Callable[[List[str]], None]) -> None:
        """Use PostgreSQL LISTEN/NOTIFY"""
        # TODO: Implement pubsub via PostgreSQL
        pass

    async def get_country_list(self) -> List[str]:
        """Get list of countries in database"""
        result = await self.db.execute(
            "SELECT DISTINCT country_id FROM documents"
        )
        return [row['country_id'] for row in result]

    async def get_country_config(self, country_id: str) -> Dict[str, Any]:
        """Get country configuration"""
        result = await self.db.execute(
            "SELECT * FROM countries WHERE id = $1",
            country_id
        )
        return dict(result[0]) if result else {}
```

---

## 7.4 Country Registry and Configuration

### Country Registry

**File:** `scripts/country_modules/registry.py`

```python
from typing import Dict, Type, Optional
from dataclasses import dataclass
from .base.scraper import BaseScraper
from .base.parser import BaseParser
from .base.sync import DocumentSync

@dataclass
class CountryModule:
    """Country-specific module configuration"""

    country_id: str                    # ISO 3166-1 alpha-3 (e.g., "RUS", "DEU")
    country_name: str
    legal_system: str                  # "civil_law", "common_law", "mixed"
    scraper_class: Type[BaseScraper]
    parser_class: Type[BaseParser]
    sync_class: Type[DocumentSync]
    data_sources: Dict[str, str]
    jurisdiction_levels: List[str]
    is_active: bool = True

# Country registry
COUNTRIES: Dict[str, CountryModule] = {
    "RUS": CountryModule(
        country_id="RUS",
        country_name="Russia",
        legal_system="civil_law",
        scraper_class=RussiaPravoScraper,
        parser_class=RussiaHtmlParser,
        sync_class=PostgreSQLSync,
        data_sources={
            "federal": "http://pravo.gov.ru",
            "supreme_court": "https://vsrf.ru",
            "constitutional_court": "http://www.ksrf.ru",
        },
        jurisdiction_levels=["federal", "regional", "municipal"],
    ),
    # Future countries:
    # "DEU": CountryModule(...),
    # "USA": CountryModule(...),
}

def get_country_module(country_id: str) -> Optional[CountryModule]:
    """Get country module by ID"""
    return COUNTRIES.get(country_id.upper())

def list_available_countries() -> List[str]:
    """Get list of available country IDs"""
    return list(COUNTRIES.keys())

def get_country_config(country_id: str) -> Dict[str, any]:
    """Get country configuration"""
    module = get_country_module(country_id)
    if not module:
        raise ValueError(f"Unknown country: {country_id}")
    return {
        'country_id': module.country_id,
        'country_name': module.country_name,
        'legal_system': module.legal_system,
        'data_sources': module.data_sources,
        'jurisdiction_levels': module.jurisdiction_levels,
        'is_active': module.is_active,
    }
```

### User Configuration

**File:** `~/.law7/config.yaml`

```yaml
# Country selection
countries:
  selected:
    - russia    # User wants Russian law
    - germany   # User wants German law (future)
    # france     # Not selected

# Sync configuration
sync:
  enabled: true
  mode: postgres  # postgres | ipfs | dpc | hybrid
  interval_hours: 24
  countries_selected_only: true  # Only sync selected countries

  # P2P configuration (for ipfs/dpc modes)
  p2p:
    bootstrap_nodes: []  # List of known peers
    max_bandwidth_mbps: 10  # Limit sync bandwidth

# Storage configuration
storage:
  postgres:
    host: localhost
    port: 5433
    database: law7

  qdrant:
    host: localhost
    port: 6333
    collection: law7

# Embeddings configuration
embeddings:
  model_path: ./models/deepvk_USER2-base
  batch_size: 32
  device: cuda  # cuda | cpu
```

---

## 7.5 MCP Server Updates

### Update MCP Tools

**File:** `src/tools/query-laws.ts`

```typescript
export const queryLawsTool = {
  name: "query-laws",
  description: "Search legal documents by country",
  inputSchema: {
    country: {
      type: "string",
      description: "Country code (e.g., 'RUS', 'DEU', 'USA'). Defaults to user's selected countries.",
    },
    query: {
      type: "string",
      description: "Search query",
    },
    filters: {
      type: "object",
      description: "Optional filters (doc_type, date_range, etc.)",
    },
    use_hybrid: {
      type: "boolean",
      description: "Use hybrid search (semantic + keyword)",
    },
  },
};
```

**File:** `src/tools/list-countries.ts`

```typescript
export const listCountriesTool = {
  name: "list-countries",
  description: "List available countries",
  inputSchema: {},
  // Returns: list of countries with metadata
};
```

---

## 7.6 Database Schema Updates

### Add country_id to existing tables

**File:** `docker/postgres/init.sql` (additions)

```sql
-- Add countries table
CREATE TABLE IF NOT EXISTS countries (
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

-- Add country_id to existing tables
ALTER TABLE documents ADD COLUMN IF NOT EXISTS country_id VARCHAR(3) NOT NULL DEFAULT 'RUS';
ALTER TABLE documents ADD CONSTRAINT IF NOT EXISTS fk_country
    FOREIGN KEY (country_id) REFERENCES countries(id);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS jurisdiction_level VARCHAR(20);
    -- 'federal', 'regional', 'municipal', 'state', etc.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(100);
    -- For federal systems: region code, state code, etc.

-- Index for country-specific queries
CREATE INDEX IF NOT EXISTS idx_documents_country ON documents(country_id, jurisdiction_level);

-- Insert Russia
INSERT INTO countries (id, name_en, name_native, legal_system_type, federal_structure, official_languages, data_sources)
VALUES ('RUS', 'Russia', 'Россия', 'civil_law', true, ARRAY['ru'],
        '{"federal": "http://pravo.gov.ru", "supreme_court": "https://vsrf.ru"}')
ON CONFLICT (id) DO NOTHING;
```

---

## 7.7 Migration Path for Russia Module

**Priority:** HIGH - Existing functionality must continue working

### Migration Steps

1. **Create new structure** without touching existing code
2. **Create base classes** with clear interfaces
3. **Create PostgreSQLSync** as reference DocumentSync implementation
4. **Move Russia module** to `country_modules/russia/`
5. **Create shims** for backward compatibility:
   ```python
   # scripts/crawler/pravo_api_client.py (shim)
   from country_modules.russia.scrapers.pravo_api_client import PravoApiClient
   # Re-export for backward compatibility
   ```
6. **Update imports** gradually
7. **Remove shims** after all imports updated
8. **Add tests** for new structure

### Backward Compatibility

- All existing scripts continue to work
- Gradual migration via shims
- No breaking changes to MCP tools
- Database migration uses default `country_id='RUS'`

---

## 7.8 Sync Coordinator

**File:** `scripts/sync/coordinator.py`

```python
from typing import List, Optional
from datetime import datetime, timedelta
from ..country_modules.base.sync import DocumentSync
from ..country_modules.base.scraper import BaseScraper
from ..country_modules.registry import get_country_module, get_country_config

class SyncCoordinator:
    """Orchestrates document synchronization"""

    def __init__(self, sync_impl: DocumentSync, config: dict):
        self.sync = sync_impl
        self.config = config

    async def sync_country(self, country_id: str,
                          since: Optional[datetime] = None) -> dict:
        """Sync a single country"""

        # Get country module
        module = get_country_module(country_id)
        if not module:
            raise ValueError(f"Unknown country: {country_id}")

        # Create scraper
        scraper = module.scraper_class()

        # Fetch updates
        updates = await scraper.fetch_updates(
            since.date() if since else None
        )

        # Publish to sync layer
        results = {
            'country_id': country_id,
            'fetched': len(updates),
            'published': 0,
            'errors': []
        }

        for doc in updates:
            try:
                await self.sync.publish_document(
                    country_id,
                    doc.doc_id,
                    doc.content,
                    doc.metadata
                )
                results['published'] += 1
            except Exception as e:
                results['errors'].append({
                    'doc_id': doc.doc_id,
                    'error': str(e)
                })

        return results

    async def sync_all_selected(self) -> dict:
        """Sync all selected countries from config"""

        selected = self.config.get('countries', {}).get('selected', [])
        results = {}

        for country_id in selected:
            try:
                results[country_id] = await self.sync_country(country_id)
            except Exception as e:
                results[country_id] = {
                    'error': str(e)
                }

        return results
```

---

## Deliverables

| Deliverable | Description |
|-------------|-------------|
| `scripts/country_modules/base/` | Base classes (scraper, parser, sync) |
| `scripts/country_modules/base/sync.py` | DocumentSync ABC |
| `scripts/country_modules/registry.py` | Country module registry |
| `scripts/country_modules/russia/` | Russia module (refactored) |
| `scripts/sync/coordinator.py` | Sync orchestration |
| `scripts/sync/postgres_sync.py` | PostgreSQLSync (reference implementation) |
| `scripts/sync/manifest.py` | Document manifest tracking |
| `~/.law7/config.yaml` | User configuration template |
| Updated MCP tools | Country-aware query tools |
| Database migration | Add countries table, country_id columns |
| Tests | Test refactoring preserves functionality |

---

## Verification Steps

After completing Phase 7:

### Structure Verification
- [ ] All base classes defined with clear interfaces
- [ ] Russia module refactored to new structure
- [ ] Backward compatibility shims in place
- [ ] All existing tests pass

### Interface Verification
- [ ] DocumentSync ABC clearly defined
- [ ] PostgreSQLSync implements DocumentSync
- [ ] BaseScraper and BaseParser defined
- [ ] Country registry functional

### Integration Verification
- [ ] User can select countries in config
- [ ] Only selected countries are synced
- [ ] MCP tools work with country parameter
- [ ] Database migration successful

### Documentation Verification
- [ ] README updated with new structure
- [ ] API documentation updated
- [ ] Migration guide documented

---

## Timeline

**Weeks 1-2:** Create base classes and interfaces
- Define DocumentSync ABC
- Define BaseScraper and BaseParser
- Create country registry

**Weeks 3-4:** Refactor Russia module
- Move existing code to new structure
- Create shims for backward compatibility
- Update imports

**Weeks 5-6:** Implement sync coordination
- Create PostgreSQLSync
- Create SyncCoordinator
- Create manifest tracking

**Weeks 7-8:** Database and MCP updates
- Add countries table
- Update MCP tools for country parameter
- Test end-to-end

---

## Related Phases

- **Enables:** [Phase 0: P2P Research](./PHASE0_P2P_RESEARCH.md) - Provides DocumentSync interface
- **Enables:** [Phase 4: Regional Legislation](./PHASE4_REGIONAL.md) - Provides country architecture

---

## Next Steps After Phase 7

1. **Measure actual data volumes:**
   - Current Russia data size (documents + embeddings)
   - Daily update size
   - To inform Phase 0 P2P requirements

2. **Start Phase 0:** Implement DocumentSync with P2P technologies

3. **Add first new country:** Germany or US (simpler legal system)

---

**Status:** Ready to start
**Owner:** TBD
**Blocked by:** None
**Blocking:** Phase 0 (P2P research), Phase 4 (multi-country expansion)
