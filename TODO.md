# Law7 TODO

## High Priority

### [MVP] Complete Testing Flow
- [x] Fix content sync to run without embeddings
- [x] Build MCP server (7 tools implemented: query-laws, get-law, list-countries, get-statistics, get-code-structure, get-article-version, trace-amendment-history)
- [x] Test content parsing from API metadata (test script: scripts/test_content_parsing.py)
- [x] Database has 156,000 documents (2022-2026) - sufficient for MVP testing
- [x] All 16 legal codes imported (Constitution + 15 codes)
- [ ] **Run content sync + embeddings** - See [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md)
  ```bash
  # Quick test with 100 docs
  poetry run python scripts/sync/content_sync.py --limit 100 --recreate-collection

  # Full run with 156k docs
  poetry run python scripts/sync/content_sync.py --recreate-collection
  ```
- [ ] Test all 7 MCP tools with real data

### Data Coverage Check
- [x] **COMPLETED**: Add consolidation engine infrastructure
  - [x] Amendment parser: extracts article changes from amendment text
  - [x] Diff engine: applies modifications, additions, repeals
  - [x] Version manager: tracks and queries article version history
  - [x] Consolidation orchestrator: coordinates consolidation process
  - [x] Database schema: code_article_versions, amendment_applications, consolidated_codes
- [x] **COMPLETED**: Update TypeScript models and MCP tools (Phase 7)
  - [x] **COMPLETED**: HTML scraper for detailed amendment text
  - [x] Extracts publication dates from text: "Дата опубликования: 29.12.2025"
  - [x] Removes duplicate text from nested HTML elements
  - [x] TypeScript MCP tools for consolidated code queries (get-code-structure, get-article-version, trace-amendment-history)
- [ ] **NEXT PHASE**: Content importer for consolidated codes (Phase 8)
  - [ ] Fetch original code from pravo.gov.ru for consolidation (consolidate.py line 92: TODO)
  - [ ] Test consolidation with real data
- [x] **COMPLETED**: Add remaining major Russian legal codes to the database
  - [x] **Civil Code** (Гражданский кодекс) - Parts 1, 2, 3, 4 - 1,732 articles
  - [x] **Criminal Code** (Уголовный кодекс) - 534 articles
  - [x] **Tax Code** (Налоговый кодекс) - Parts 1 and 2 - 21 articles
  - [x] **Administrative Code** (КоАП) - 414 articles
  - [x] **Family Code** (Семейный кодекс) - 177 articles
  - [x] **Housing Code** (Жилищный кодекс) - 198 articles
  - [x] **Land Code** (Земельный кодекс) - 61 articles
  - [x] **Constitution** (Конституция) - 34 articles
  - [x] **Civil Procedure Code** (ГПК) - 494 articles
  - [x] **Arbitration Procedure Code** (АПК) - 418 articles
  - [x] **Criminal Procedure Code** (УПК) - 553 articles
- [x] **COMPLETED**: Check if codes can be imported from official sources
  - [x] kremlin.ru (official publication portal) - primary source
  - [x] pravo.gov.ru (official publication portal) - fallback
  - [x] government.ru - fallback for some codes
- [x] **COMPLETED**: Document the source URLs for code imports (see CODE_METADATA)

## Medium Priority

### Consolidation Engine ✅ INFRASTRUCTURE COMPLETED
**Status**: Core infrastructure is in place, needs content import

**Completed (Phase 1-6)**:
- [x] Historical sync support (2011-2022 via `initial_sync.py --start-date`)
- [x] Database schema for consolidation (3 tables + indexes)
- [x] 8 core Russian codes metadata in database
- [x] Amendment parser (`scripts/consolidation/amendment_parser.py`)
- [x] Article diff engine (`scripts/consolidation/diff_engine.py`)
- [x] Version manager (`scripts/consolidation/version_manager.py`)
- [x] Consolidation orchestrator (`scripts/consolidation/consolidate.py`)

**Next Steps (Phase 8)**:
- [x] HTML scraper for detailed amendment text (completed)
- [x] TypeScript/MCP tools for consolidated code queries (completed)
- [ ] Content importer for consolidated codes (fetch original code from pravo.gov.ru)
- [ ] Test consolidation with real data

**Benefits**:
- **Version history**: Query any article as it existed on any date
- **Amendment tracking**: See which law changed which article
- **Official source**: Uses free pravo.gov.ru data (2011-present)

### Embeddings Model Upgrade ✅ COMPLETED
**Current**: `deepvk/USER2-base` (768 dims, CUDA-accelerated)

**Completed Changes:**
- [x] Updated `.env`: `EMBEDDING_DEVICE=cuda`, `EMBEDDING_MODEL=deepvk/USER2-base`
- [x] Updated `pyproject.toml`: Added `torch` with CUDA support
- [x] Updated `scripts/indexer/embeddings.py`: Added prompt_name support for USER2-base
- [x] Changed Qdrant vector size from 1024 to 768
- [x] Tested embeddings generation with GPU (RTX 3060 12GB)

**Benefits:**
- **8192 token context** - Can process full legal documents without chunking
- **Russian-specific** (RuModernBERT based) - Optimized for Russian text
- **3.7x faster** (149M params vs 560M)
- **GPU-accelerated** on RTX 3060 12GB

**To re-generate all embeddings:**
```bash
# Already tested with 5 documents - working
# For full 4,600 documents:
poetry run python scripts/sync/content_sync.py --recreate-collection
```

### OCR Enhancement (See question)
- [ ] Install Tesseract OCR for scanned PDFs
- [ ] Test OCR quality on Russian legal documents
- [ ] Add OCR fallback for documents with short API metadata

Question: Can we use https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B or from ollama running loccaly for this ?

## Low Priority

### MCP Server Enhancements
- [x] **Improved keyword search**: OR fallback when AND returns no results (2025-01-21)
- [ ] Implement hybrid search (keyword + semantic combined)
  - Note: `use_hybrid` parameter exists in schema but not implemented
  - Requires: Embedding generation in MCP server (currently only in Python pipeline)
  - Requires: Combine Qdrant semantic + PostgreSQL keyword results
- [ ] Add document summarization tool
- [ ] Add document comparison tool
- [ ] Add date range filtering in query-laws tool
  - Note: `getDocumentsByDateRange()` function exists in postgres.ts but not exposed as MCP tool

### Code Import Issues
- [ ] **Fix KoAP_RF (Administrative Code) import**
  - **Issue**: Currently contains Budget Code (БК РФ) content instead of Administrative Code (КоАП РФ) content
  - **Root cause**: pravo_nd (102074277) may be incorrect, or kremlin.ru source not accessible
  - **Blocked**: kremlin.ru not responding from current network, pravo.gov.ru timing out
  - **Action needed**: Retry when government sites accessible, or find correct official source URL

### Data Pipeline
- [ ] **URGENT**: Fix historical sync date range filtering
  - **Issue**: `initial_sync.py --start-date 2011-01-01 --end-date 2022-08-28` doesn't filter by date
  - **Root cause**: API returns all documents (1.6 million total, 53,142 pages) in reverse chronological order
  - **Current behavior**: Syncs from newest (2026) → oldest, taking 100+ hours for full sync
  - **Proposed solution**: Reverse pagination - start from last page (oldest docs) and move forward
  - **Filtering needed**: Consider document type, block, or other filters to reduce scope
  - **Notes**:
    - 156k documents already synced (2022-2026) - sufficient for current testing
    - API response: `itemsTotalCount: 1594246`, `pagesTotalCount: 53142`
    - See `data/raw/Documents.json` for API structure
- [ ] Add incremental sync (only new documents)
- [ ] Add change detection via text_hash
- [ ] Add retry logic for failed API requests
- [ ] Add progress resumption after interruption

### Performance
- [ ] Optimize batch sizes for RTX 3060
- [ ] Add concurrent processing for embeddings
- [ ] Add caching for frequently accessed documents
