# Law7 TODO

## High Priority

### [MVP] Complete Testing Flow
- [x] Fix content sync to run without embeddings (in progress)
- [ ] Test content parsing from API metadata
- [ ] Build and test MCP server
- [ ] Test all 4 MCP tools with real data

### Data Coverage Check
- [ ] **HIGH PRIORITY**: Add all major Russian legal codes to the database
  - **Civil Code** (Гражданский кодекс) - Parts 1, 2, 3, 4
  - **Criminal Code** (Уголовный кодекс)
  - **Labor Code** (Трудовой кодекс) - Full text needed
  - **Tax Code** (Налоговый кодекс) - Parts 1 and 2
  - **Administrative Code** (КоАП об административных правонарушениях)
  - **Family Code** (Семейный кодекс)
  - **Land Code** (Земельный кодекс)
- [ ] Check if codes can be imported from official sources (consultantplus, garant, etc.)
- [ ] Research if pravo.gov.ru has any full code texts or only amendments
- [ ] Document the source URLs for code imports

## Medium Priority

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
- [ ] Add hybrid search (keyword + semantic combined)
- [ ] Add document summarization tool
- [ ] Add document comparison tool
- [ ] Add date range filtering in query-laws tool

### Data Pipeline
- [ ] Add incremental sync (only new documents)
- [ ] Add change detection via text_hash
- [ ] Add retry logic for failed API requests
- [ ] Add progress resumption after interruption

### Performance
- [ ] Optimize batch sizes for RTX 3060
- [ ] Add concurrent processing for embeddings
- [ ] Add caching for frequently accessed documents
