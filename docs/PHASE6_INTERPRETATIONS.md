# Phase 6: Official Interpretations

**Duration:** Months 10-12
**Priority:** MEDIUM
**Status:** Not Started

---

## Overview

Add official government agency interpretations (ministry letters, guidance) that provide authoritative but non-binding clarification on laws.

---

## 6.1 Database Schema for Ministry Letters

**Priority:** MEDIUM - Important for tax/labor law guidance

### New Tables

```sql
-- Official interpretations
CREATE TABLE official_interpretations (
    id UUID PRIMARY KEY,
    agency_name VARCHAR(200),
    agency_type VARCHAR(50),
    document_type VARCHAR(50), -- letter, guidance, instruction
    document_number VARCHAR(100),
    document_date DATE,
    title TEXT,
    question TEXT,
    answer TEXT,
    full_content TEXT,
    legal_topic VARCHAR(100),
    related_laws JSONB,
    binding_nature VARCHAR(50),
    validity_status VARCHAR(50),
    supersedes UUID[],
    superseded_by UUID,
    source_url TEXT,
    vector_embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Government agencies
CREATE TABLE government_agencies (
    id UUID PRIMARY KEY,
    agency_name VARCHAR(200),
    agency_type VARCHAR(50),
    parent_agency_id UUID,
    jurisdiction VARCHAR(100),
    website VARCHAR(200),
    is_active BOOLEAN
);
```

### Files to Modify

- `docker/postgres/init.sql` (add interpretation tables)

---

## 6.2 Ministry Letter Scraper

**Priority:** MEDIUM - Fetch official interpretations

### Target Agencies (Tier 1)

1. Ministry of Finance (Минфин) - Tax law interpretations
2. Federal Tax Service (ФНС) - Tax procedure clarifications
3. Rostrud - Labor law interpretations

### Implementation

```python
# scripts/crawler/ministry_scraper.py
class MinistryScraper:
    """Scrape ministry official letters and guidance"""

    def __init__(self, agency_name: str):
        self.agency_name = agency_name
        self.base_url = self.get_agency_url(agency_name)

    def get_agency_url(self, agency_name: str) -> str:
        """Map agency to website URL"""
        # Minfin: https://minfin.gov.ru/ru/document/
        # FNS: https://www.nalog.gov.ru/rn77/about_fts/docs/
        # Rostrud: https://rostrud.gov.ru/legal/letters/
        pass

    def fetch_letters(self, start_date: date, end_date: date):
        """Fetch all letters within date range"""
        pass
```

### Files to Create

- `scripts/crawler/ministry_scraper.py`
- `scripts/parser/ministry_parser.py`
- `scripts/import/import_ministry_letters.py`

---

## 6.3 MCP Tools for Official Interpretations

**Priority:** MEDIUM - Expose interpretations to AI assistants

### New MCP Tools

```typescript
// src/tools/search-interpretations.ts
export const searchInterpretations = {
  name: "search-interpretations",
  description: "Search official ministry interpretations",
  inputSchema: {
    query: "string",
    agency: "optional agency filter",
    legal_topic: "optional topic filter"
  }
};
```

### Files to Create

- `src/tools/search-interpretations.ts`
- `src/models/interpretation.ts`

---

## Deliverables

- Interpretation database schema
- Ministry scrapers (Minfin, FNS, Rostrud)
- MCP tools for interpretation queries
- ~3,000-5,000 ministry letters imported

---

## Related Phases

- **Requires:** [Phase 1](./PHASE1_FOUNDATION.md) (tests)
- **References:** [Phase 5](./PHASE5_COURTS.md) (court practice cited in interpretations)

---

## Timeline

**Month 10:** Database schema, scraper framework
**Month 11:** Import Minfin, FNS letters
**Month 12:** Import Rostrud letters, testing

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** Phase 1 (tests)
**Blocking:** None (completeness improvement)
