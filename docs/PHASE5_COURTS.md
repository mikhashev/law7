# Phase 5: Judicial Practice Integration

**Duration:** Months 7-9
**Priority:** HIGH
**Status:** Not Started

---

## Overview

Integrate Supreme Court and Constitutional Court decisions, providing authoritative interpretations of laws for AI assistants.

---

## 5.1 Database Schema for Court Decisions

**Priority:** HIGH - Required for Supreme/Constitutional Court data

### New Tables

```sql
-- Court decisions
CREATE TABLE court_decisions (
    id UUID PRIMARY KEY,
    court_type VARCHAR(50),     -- supreme, constitutional
    court_level VARCHAR(50),    -- federal, regional, district
    decision_type VARCHAR(50),  -- plenary_resolution, ruling, determination, review
    case_number VARCHAR(100),
    decision_date DATE,
    publication_date DATE,
    title TEXT,
    summary TEXT,
    full_text TEXT,
    legal_issues TEXT[],
    articles_interpreted JSONB,
    binding_nature VARCHAR(50), -- mandatory, persuasive, informational
    supersedes UUID[],
    superseded_by UUID,
    status VARCHAR(50),
    source_url TEXT,
    vector_embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Practice reviews
CREATE TABLE practice_reviews (
    id UUID PRIMARY KEY,
    court_type VARCHAR(50),
    review_title TEXT,
    publication_date DATE,
    period_covered VARCHAR(100),
    content TEXT,
    key_conclusions TEXT[],
    common_errors TEXT[],
    correct_approach TEXT[],
    cases_analyzed INTEGER,
    source_url TEXT,
    vector_embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Legal positions (for Constitutional Court)
CREATE TABLE legal_positions (
    id UUID PRIMARY KEY,
    decision_id UUID,
    position_text TEXT,
    constitutional_basis TEXT[],
    laws_affected TEXT[],
    position_date DATE,
    still_valid BOOLEAN,
    vector_embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Files to Modify

- `docker/postgres/init.sql` (add court tables)

---

## 5.2 Court Decision Scraper

**Priority:** HIGH - Fetch Supreme/Constitutional Court decisions

### Implementation

```python
# scripts/crawler/court_scraper.py
class SupremeCourtScraper:
    """Scrape Supreme Court of Russian Federation"""

    def fetch_plenary_resolutions(self):
        """Fetch all Постановления Пленума"""
        # https://vsrf.ru/documents/own/
        pass

    def fetch_practice_reviews(self, year, quarter):
        """Fetch Обзоры судебной практики"""
        # https://vsrf.ru/documents/practice/
        pass

class ConstitutionalCourtScraper:
    """Scrape Constitutional Court decisions"""

    def fetch_rulings(self):
        """Fetch all Постановления КС РФ"""
        # http://www.ksrf.ru/ru/Decision/
        pass

    def fetch_determinations(self):
        """Fetch Определения with significant legal positions"""
        pass
```

### Files to Create

- `scripts/crawler/court_scraper.py`
- `scripts/parser/court_parser.py`
- `scripts/import/import_court_decisions.py`

---

## 5.3 MCP Tools for Judicial Practice

**Priority:** HIGH - Expose court decisions to AI assistants

### New MCP Tools

```typescript
// src/tools/search-court-decisions.ts
export const searchCourtDecisions = {
  name: "search-court-decisions",
  description: "Search court decisions by query or legal issue",
  inputSchema: {
    query: "string",
    court_type: "supreme | constitutional",
    decision_type: "optional filter"
  }
};

// src/tools/get-supreme-court-resolution.ts
export const getSupremeCourtResolution = {
  name: "get-supreme-court-resolution",
  description: "Get specific Supreme Court plenary resolution",
  inputSchema: {
    resolution_number: "string",
    decision_date: "optional date"
  }
};
```

### Files to Create

- `src/tools/search-court-decisions.ts`
- `src/tools/get-supreme-court-resolution.ts`
- `src/models/court.ts`

---

## Deliverables

- Court decision database schema
- Supreme Court scraper (resolutions, reviews)
- Constitutional Court scraper (rulings, determinations)
- MCP tools for judicial practice queries
- ~500-1,000 court decisions imported

---

## Related Phases

- **Requires:** [Phase 1](./PHASE1_FOUNDATION.md) (tests)
- **References:** [Phase 4](./PHASE4_REGIONAL.md) (regional laws often referenced)

---

## Timeline

**Month 7:** Database schema, scraper framework
**Month 8:** Import Supreme Court decisions
**Month 9:** Import Constitutional Court, testing

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** Phase 1 (tests)
**Blocking:** Phase 6 (interpretations often cite court practice)
