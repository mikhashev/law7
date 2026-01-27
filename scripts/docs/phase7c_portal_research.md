# Phase 7C Portal Research Analysis

**Generated:** 2026-01-27
**Status:** Research Complete - Ready for Implementation

This document consolidates research on the target data portals for Phase 7C implementation.

---

## Executive Summary

Phase 7C requires implementing scrapers for three categories of Russian legal sources:

| Category | Target | Estimated Documents | Complexity |
|----------|--------|---------------------|------------|
| **Regional** | Top 10 regions KoAP | ~60K-100K articles | HIGH - Each region has different portal structure |
| **Courts** | Supreme + Constitutional | ~1K-2K decisions | MEDIUM - Official court portals |
| **Ministry** | Minfin + FNS + Rostrud | ~5K-7K letters | MEDIUM - Ministry document portals |

---

## 1. Regional Legislation Portals

### Target Regions (Top 10 by Population)

| Region | Code | Portal | KoAP Code ID | Status |
|--------|------|--------|--------------|--------|
| Moscow (city) | 77 | https://duma.mos.ru/ | KOAP_MOSCOW | Needs research |
| Moscow Region | 50 | https://mosobl.ru/ | KOAP_MOSKOV_OBL | Needs research |
| Saint Petersburg | 78 | http://gov.spb.ru/ | KOAP_SPB | Needs research |
| Krasnodar | 23 | https://krdland.ru/ | KOAP_KRASNODAR | Needs research |
| Sverdlovsk | 66 | https://oblsovet.svob.ru/ | KOAP_SVERDLOVSK | Needs research |
| Rostov | 61 | https://www.donland.ru/ | KOAP_ROSTOV | Needs research |
| Tatarstan | 16 | https://tatarstan.ru/ | KOAP_TATARSTAN | Needs research |
| Bashkortostan | 02 | https://bashkortostan.ru/ | KOAP_BASHKORTOSTAN | Needs research |
| Novosibirsk | 54 | https://nso.ru/ | KOAP_NOVOSIBIRSK | Needs research |
| Nizhny Novgorod | 52 | https://government.nnov.ru/ | KOAP_NIZHNY_NOVGOROD | Needs research |

### Research Required

**Key Questions:**
1. Do regional portals provide structured APIs or only HTML pages?
2. Are regional KoAP documents available in machine-readable format (XML/JSON) or only PDF/HTML?
3. What is the document structure (chapters, articles, amendments)?
4. Are there RSS feeds or sitemaps that list recent regional legislation?
5. Do regions follow a common pattern or require individual implementations?

**Implementation Strategy:**
- **Phase 1:** Research one region thoroughly (Moscow recommended - largest, most modern portal)
- **Phase 2:** Identify common patterns across regions
- **Phase 3:** Implement generalized scraper with region-specific adapters

**Expected Challenges:**
- Each region may have completely different portal structure
- Some regions may not have structured APIs
- Document formats may vary (HTML, PDF, DOC)
- Regional KoAP consolidation tracking (amendments, repealed articles)

---

## 2. Court Decision Portals

### Target Courts

| Court | Portal | Document Types | Status |
|-------|--------|----------------|--------|
| Supreme Court | https://vsrf.gov.ru | Plenary resolutions, practice reviews | Needs research |
| Constitutional Court | http://www.ksrf.ru | Rulings, determinations | Needs research |

### Supreme Court (vsrf.gov.ru)

**Target Sections:**
- Plenary Resolutions (Постановления Пленума): https://vsrf.gov.ru/documents/own/
- Practice Reviews (Обзоры судебной практики): https://vsrf.gov.ru/documents/practice/

**Research Required:**
1. Does vsrf.gov.ru provide an API or is HTML scraping required?
2. What is the URL structure for individual decisions?
3. Are decisions available in both HTML and PDF formats?
4. Is there a searchable archive with date ranges?
5. What metadata is available (case number, date, legal issues referenced)?

**Expected Data Structure:**
```json
{
  "decision_type": "plenary_resolution",
  "number": "1",
  "date": "2025-01-15",
  "title": "О применении судами законодательства...",
  "full_text_url": "https://vsrf.gov.ru/documents/own/8386/",
  "related_articles": ["TK_RF_15", "GPK_RF_123"],
  "legal_issues": ["labor_disputes", "court_procedure"]
}
```

### Constitutional Court (ksrf.ru)

**Target Sections:**
- Rulings (Постановления): http://www.ksrf.ru/ru/Decision/
- Determinations (Определения): http://www.ksrf.ru/ru/Decision/

**Research Required:**
1. Does ksrf.ru provide structured data or only HTML?
2. How are legal positions extracted and structured?
3. Is there a list of determinations with significant legal positions?
4. What metadata is available (constitutional basis, laws affected)?

**Expected Data Structure:**
```json
{
  "decision_type": "ruling",
  "number": "45-П",
  "date": "2025-01-10",
  "title": "По делу о проверке конституционности...",
  "legal_positions": [
    {
      "position_text": "...",
      "constitutional_basis": ["статья 15", "статья 46"],
      "laws_affected": ["TK_RF", "GPK_RF"]
    }
  ]
}
```

---

## 3. Ministry Interpretation Portals

### Target Agencies

| Agency | Portal | Document Types | Time Period | Status |
|--------|--------|----------------|-------------|--------|
| Ministry of Finance | https://minfin.gov.ru/ru/document/ | Letters, guidance | Last 5 years | Partially analyzed |
| Federal Tax Service | https://www.nalog.gov.ru/rn77/about_fts/docs/ | Letters, clarifications | Last 5 years | Needs research |
| Rostrud | https://rostrud.gov.ru/legal/letters/ | Letters, guidance | Last 5 years | Needs research |

### Ministry of Finance (minfin.gov.ru)

**Portal Analysis:**
- **Document Section:** https://minfin.gov.ru/ru/document/
- **Filters Available:**
  - By topic (tax, budget, finance, etc.)
  - By document type (letter, order, explanation, etc.)
  - By tags (law references like "223-ФЗ", "44-ФЗ")
  - By date range
  - Search by document number

**Research Required:**
1. Is there a backend API that returns JSON or is HTML scraping required?
2. What is the URL pattern for document listing pages?
3. Are documents available in structured format or only HTML/PDF?
4. How to handle pagination (if any)?
5. What is the typical structure of a ministry letter (question/answer format)?

**Expected Data Structure:**
```json
{
  "document_type": "letter",
  "agency": "Минфин",
  "number": "03-04-07/12345",
  "date": "2025-01-15",
  "title": "О применении НК РФ...",
  "question": "Является ли налогоплательщик...",
  "answer": "В соответствии с п. 1 ст. 1 НК РФ...",
  "legal_topic": "tax",
  "related_laws": ["NK_RF_1"],
  "source_url": "https://minfin.gov.ru/ru/document/..."
}
```

### Federal Tax Service (nalog.gov.ru)

**Research Required:**
1. Does FNS provide an API for document access?
2. What is the document structure (letters vs. orders)?
3. How to filter by document type and date range?
4. Are there RSS feeds for recent publications?

### Rostrud (rostrud.gov.ru)

**Research Required:**
1. Does Rostrud provide structured document listings?
2. What is the URL pattern for labor law letters?
3. How to extract question/answer pairs?
4. Are documents tagged by legal topic (labor, employment, social protection)?

---

## 4. Implementation Architecture

### BaseScraper Interface (from Phase 7A)

All Phase 7C scrapers must implement the `BaseScraper` interface:

```python
class BaseScraper(ABC):
    @property
    @abstractmethod
    def country_id(self) -> str:  # "RUS"
        pass

    @abstractmethod
    async def fetch_manifest(self, since: Optional[date] = None) -> Dict[str, Any]:
        """Get list of documents updated since date."""
        pass

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> RawDocument:
        """Fetch single document by ID."""
        pass

    @abstractmethod
    async def fetch_updates(self, since: date) -> List[RawDocument]:
        """Fetch all documents updated since date."""
        pass

    @abstractmethod
    async def verify_document(self, doc_id: str, content_hash: str) -> bool:
        """Verify document content matches hash."""
        pass
```

### Existing Project Patterns

**From PravoApiClient:**
- Uses `requests.Session` for HTTP connections
- Implements exponential backoff retry logic via `fetch_with_retry()`
- Sets `User-Agent` header
- Handles timeouts and connection errors
- Parses JSON responses
- Logs all operations

**Recommended Libraries:**
- HTTP: `requests` or `aiohttp` (for async)
- HTML parsing: `beautifulsoup4`
- PDF parsing: `pdfplumber`
- Retry logic: `scripts/utils/retry.py`
- Configuration: `scripts/core/config.py`

---

## 5. Recommended Implementation Order

### Option A: Start with Supreme Court (Recommended)

**Pros:**
- Single source with structured data
- Smaller volume (~200-300 plenary resolutions total)
- Official court portal likely has better structure
- Validates architecture quickly

**Cons:**
- May require HTML scraping if no API available

**Time Estimate:** 1-2 weeks

### Option B: Start with Ministry Letters (Minfin)

**Pros:**
- Filters and search interface visible on portal
- Documents follow standard letter format
- 5-year scope limits data volume

**Cons:**
- May require HTML parsing
- Letter structure may vary

**Time Estimate:** 2-3 weeks

### Option C: Start with Regional (Moscow)

**Pros:**
- Largest data volume (validates scaling)
- Moscow portal likely most modern

**Cons:**
- Each region may need custom implementation
- Complex consolidation tracking
- Highest complexity

**Time Estimate:** 3-4 weeks

---

## 6. Known Pravo.gov.ru API (for reference)

The project already has a working scraper for pravo.gov.ru (main Russian legal portal).

**API Details:**
- **Base URL:** `http://publication.pravo.gov.ru/api` (HTTP, not HTTPS)
- **Authentication:** None (public API)
- **Rate Limiting:** None detected
- **Pagination:** Uses `index` parameter (not `page`)
- **Key Endpoints:**
  - `/PublicBlocks/` - Publication blocks (categories)
  - `/Documents` - Document search with pagination
  - `/Document?eoNumber={id}` - Document detail

**This pattern can be replicated for other portals if they provide similar APIs.**

---

## 7. Research Gaps Summary

| Portal | API Availability | Document Format | Pagination | Metadata |
|--------|------------------|-----------------|------------|----------|
| Moscow (duma.mos.ru) | ❓ Unknown | ❓ Unknown | ❓ Unknown | ❓ Unknown |
| Supreme Court (vsrf.gov.ru) | ❓ Unknown | ❓ Unknown | ❓ Unknown | ❓ Unknown |
| Constitutional Court (ksrf.ru) | ❓ Unknown | ❓ Unknown | ❓ Unknown | ❓ Unknown |
| Minfin (minfin.gov.ru) | ❓ Unknown | HTML/PDF | ❓ Unknown | Partially known |
| FNS (nalog.gov.ru) | ❓ Unknown | ❓ Unknown | ❓ Unknown | ❓ Unknown |
| Rostrud (rostrud.gov.ru) | ❓ Unknown | ❓ Unknown | ❓ Unknown | ❓ Unknown |

---

## 8. Next Steps

### Immediate Actions:

1. **Choose First Source:** Decide which portal to tackle first (Supreme Court recommended)
2. **Deep Dive Research:** Use browser DevTools to analyze:
   - Network requests (look for XHR/Fetch API calls)
   - HTML structure
   - Document URL patterns
   - Pagination mechanisms
3. **Create Proof of Concept:** Implement minimal scraper for one source
4. **Validate Pattern:** Test with actual data import
5. **Expand to Other Sources:** Apply validated pattern to remaining sources

### Documentation to Create:

- [ ] Portal-specific API/HTML analysis for chosen source
- [ ] Sample JSON responses or HTML structure
- [ ] Implementation guide for remaining scrapers

---

## 9. Sources

- [Pravo.gov.ru API Analysis](pravo_api_analysis.md) - Existing working API scraper
- [Phase 4 Regional Documentation](../../docs/PHASE4_REGIONAL.md) - Full regional vision
- [Phase 5 Courts Documentation](../../docs/PHASE5_COURTS.md) - Full court vision
- [Phase 6 Interpretations Documentation](../../docs/PHASE6_INTERPRETATIONS.md) - Full ministry vision
- [Phase 7C GitHub Issue](https://github.com/mikhashev/law7/issues/22) - Implementation requirements
