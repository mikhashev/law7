# Phase 4: Regional Legislation Support

**Duration:** Months 4-6
**Priority:** HIGH
**Status:** Not Started

---

## Overview

Add support for regional Russian legislation, starting with regional administrative codes (KoAP) for the top 10 regions by population. This covers 70-80% of citizen legal questions.

---

## 4.1 Database Schema Extension

**Priority:** HIGH - Required for regional laws

### New Tables

```sql
-- Regional documents
CREATE TABLE regional_documents (
    id UUID PRIMARY KEY,
    region_id VARCHAR(10),      -- OKATO or FIAS code
    region_name VARCHAR(200),
    jurisdiction_level VARCHAR(20), -- regional, municipal
    document_type VARCHAR(50),
    document_number VARCHAR(100),
    document_date DATE,
    title TEXT,
    content TEXT,
    status VARCHAR(50),
    effective_from DATE,
    effective_until DATE,
    source_url TEXT,
    vector_embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Regional codes (KoAP)
CREATE TABLE regional_codes (
    id UUID PRIMARY KEY,
    code_id VARCHAR(50),        -- e.g., "KOAP_MOSCOW"
    region_id VARCHAR(10),
    code_name VARCHAR(200),
    adoption_date DATE,
    last_amendment_date DATE,
    consolidation_status VARCHAR(50)
);

-- Regional code articles
CREATE TABLE regional_code_articles (
    id UUID PRIMARY KEY,
    code_id VARCHAR(50),
    article_number VARCHAR(20),
    chapter_number VARCHAR(20),
    article_title TEXT,
    article_content TEXT,
    status VARCHAR(50),
    effective_from DATE,
    effective_until DATE,
    vector_embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Files to Modify

- `docker/postgres/init.sql` (add regional tables)

---

## 4.2 Regional Legislation Scraper

**Priority:** HIGH - Required for regional KoAP

### Implementation

```python
# scripts/crawler/regional_scraper.py
class RegionalScraper:
    """Scrape regional legislation from official portals"""

    def __init__(self, region_id: str):
        self.region_id = region_id
        self.base_url = self.get_region_portal_url(region_id)

    def get_region_portal_url(self, region_id: str) -> str:
        """Map region ID to official portal URL"""
        # Moscow: https://duma.mos.ru/
        # SPb: http://gov.spb.ru/
        # Pattern: {region}.gov.ru for most
        pass

    def fetch_regional_koap(self, region_id: str):
        """Fetch regional administrative code"""
        # Identify KoAP document
        # Fetch all articles
        # Parse structure
        # Store in regional_code_articles
        pass
```

### Target Regions (Phase 1 - Top 10 by population)

1. Moscow city
2. Moscow region
3. Saint Petersburg
4. Krasnodar region
5. Sverdlovsk region
6. Rostov region
7. Republic of Tatarstan
8. Republic of Bashkortostan
9. Novosibirsk region
10. Nizhny Novgorod region

### Files to Create

- `scripts/crawler/regional_scraper.py`
- `scripts/import/import_regional_koap.py`

---

## 4.3 MCP Tools for Regional Law

**Priority:** HIGH - Expose regional data to AI assistants

### New MCP Tools

```typescript
// src/tools/get-regional-law.ts
export const getRegionalLaw = {
  name: "get-regional-law",
  description: "Get regional legislation by region and document number",
  inputSchema: {
    region_id: "string",
    document_number: "string"
  }
};

// src/tools/search-regional-law.ts
export const searchRegionalLaw = {
  name: "search-regional-law",
  description: "Search regional legislation by query",
  inputSchema: {
    region_id: "string",
    query: "string",
    filters: "optional search filters"
  }
};

// src/tools/get-regional-koap-article.ts
export const getRegionalKoapArticle = {
  name: "get-regional-koap-article",
  description: "Get specific article from regional administrative code",
  inputSchema: {
    region_id: "string",
    article_number: "string"
  }
};
```

### Files to Create

- `src/tools/get-regional-law.ts`
- `src/tools/search-regional-law.ts`
- `src/tools/get-regional-koap-article.ts`
- `src/models/regional.ts` (TypeScript interfaces)

---

## Deliverables

- Regional database schema
- Regional legislation scraper for 10 regions
- MCP tools for regional law queries
- ~50,000-70,000 regional articles imported

---

## Related Phases

- **Requires:** [Phase 1](./PHASE1_FOUNDATION.md) (tests)
- **Parallel with:** [Phase 7](./PHASE7_STRUCTURE_REFACTORING.md)

---

## Timeline

**Month 4:** Database schema, scraper framework
**Month 5:** Import top 10 regions
**Month 6:** MCP tools, testing

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** Phase 1 (tests), Phase 7 (country architecture)
**Blocking:** Phase 5-6 (jurisprudence often references regional laws)
