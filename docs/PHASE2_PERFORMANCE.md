# Phase 2: Critical Performance Fixes

**Duration:** Weeks 5-8
**Priority:** HIGH
**Status:** Not Started

---

## Overview

Fix critical performance bottlenecks and complete unfinished features that block data quality and user experience.

---

## 2.1 Fix Historical Sync Date Filtering

**Priority:** HIGH - Blocking historical data import (2011-2022)

### Problem

`scripts/sync/initial_sync.py --start-date 2011-01-01 --end-date 2022-08-28` doesn't filter by date, causing 100+ hour sync times.

### Root Cause

API returns all 1.6M documents in reverse chronological order; date filter not applied to pagination.

### Solution

```python
# scripts/sync/initial_sync.py
def calculate_start_page(start_date: str) -> int:
    """Calculate starting page from date based on document count"""
    # API returns ~30 docs per page, reverse chronological
    # 1.6M docs / 30 ≈ 53,142 pages
    # Need to calculate approximate page for start_date
    pass

def sync_with_date_filter(start_date: str, end_date: str):
    """Sync only documents within date range"""
    start_page = calculate_start_page(start_date)
    # Forward pagination from start_page
    # Filter by date in loop
    pass
```

### Files to Modify

- `scripts/sync/initial_sync.py` (lines with date filtering logic)

### Verification

- Test with 2015-2016 date range (should complete in <1 hour)
- Verify all documents are within specified date range
- Check no duplicates on re-run

---

## 2.2 Complete Consolidation Engine Content Import

**Priority:** HIGH - Infrastructure complete, needs content

### Current State

- All consolidation infrastructure exists (parser, diff engine, version manager)
- Selenium WebDriver for full document fetching implemented in commit `f98b887`
- TODO at line 92 for original code fetching

### Use Existing Selenium Implementation

From commit `f98b887` (feat(parser): add Selenium WebDriver support):
- `PravoContentParser.fetch_with_selenium()` - Fetches complete document text from pravo.gov.ru iframes
- Handles Windows-1251 encoding for Cyrillic text
- Extracts structured HTML content after JavaScript execution
- Already tested on document `0001202405140009`

### Implementation Steps

```python
# scripts/consolidation/consolidate.py:92
def fetch_original_code_from_pravo(code_id: str) -> str:
    """
    Fetch original code publication from pravo.gov.ru using Selenium.
    Leverages existing PravoContentParser.fetch_with_selenium().
    """
    from parser.html_parser import PravoContentParser

    # Get original publication eoNumber for this code
    # e.g., GK RF Part 1: 0001199411...

    parser = PravoContentParser()
    content = parser.fetch_with_selenium(eo_number)

    # Parse article structure from content
    # Return structured text
    pass
```

### Files to Modify

- `scripts/consolidation/consolidate.py` (implement TODO at line 92, use Selenium)
- `scripts/consolidation/consolidate.py` (implement TODO at line 167)

### Verification

- Successfully fetch and parse 1 complete code (GK RF)
- Verify article structure matches expected format
- Test consolidation with 3-5 amendments applied

---

## 2.3 Implement Hybrid Search

**Priority:** MEDIUM - Improves search quality

### Current State

`use_hybrid` parameter exists in schema but not implemented

### Implementation

```typescript
// src/tools/query-laws.ts
async function hybridSearch(query: string, filters: SearchFilters) {
  // 1. Generate embedding for query (need to add embedding gen to MCP server)
  // 2. Run semantic search (Qdrant)
  // 3. Run keyword search (PostgreSQL trigram)
  // 4. Combine results with score fusion
  // 5. Return ranked results
}
```

### Challenges

- Need to add embedding generation to TypeScript (currently only in Python)
- Requires `sentence-transformers` or equivalent in Node.js
- Or use embeddings stored in Qdrant (already generated)

### Alternative Approach: Use pre-generated embeddings

- Document embeddings already in Qdrant
- Need query embedding generation in Node.js
- Options:
  1. Call Python embedding service via API
  2. Use ONNX runtime for USER2-base in Node.js
  3. Use OpenAI/Cohere embeddings (not ideal for offline)

### Files to Modify

- `src/tools/query-laws.ts` (implement hybrid search)
- `src/embeddings/embedding.ts` (new - query embedding generation)
- `package.json` (add embedding dependencies)

---

## Deliverables

- Historical sync working with date filtering (unlocks 2011-2022 data)
- Consolidation engine with original code content
- Hybrid search combining semantic + keyword search

---

## Related Phases

- **Requires:** [Phase 1](./PHASE1_FOUNDATION.md) (test coverage)
- **Enables:** [Phase 3](./PHASE3_OCR.md) (better data quality for search)

---

## Timeline

**Week 5-6:** Fix historical sync date filtering
**Week 7:** Complete consolidation engine
**Week 8:** Implement hybrid search

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** Phase 1 (tests)
**Blocking:** Phase 3-6 (performance impacts all features)
