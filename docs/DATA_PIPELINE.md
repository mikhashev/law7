# Law7 Data Pipeline Guide

This guide explains how to populate and maintain the Law7 database with legal documents from official Russian government sources.

## Official Data Sources

The Law7 data pipeline uses only official Russian government sources for legal documents:

| Source | URL | Purpose | Documents |
|--------|-----|---------|-----------|
| **pravo.gov.ru** | http://pravo.gov.ru/ | Official Russian legal publication portal (primary API source) | Federal laws, presidential decrees, government resolutions |
| **kremlin.ru** | http://kremlin.ru/ | Presidential administration website | Constitution, presidential decrees (KONST_RF) |
| **government.ru** | http://government.ru/ | Government website | Government resolutions, procedure codes (APK_RF, GPK_RF, UPK_RF) |

### Source Details

**pravo.gov.ru** (Primary)
- Official portal for legal publications
- Provides REST API for document access
- Contains federal laws, decrees, resolutions from 2011-present
- Document metadata includes: type, number, date, signing authority
- API endpoint: `http://publication.pravo.gov.ru/api`

**kremlin.ru**
- Source for the Russian Constitution
- Presidential decrees and orders
- Used for importing KONST_RF code

**government.ru**
- Government resolutions and orders
- Procedural codes (arbitration, civil procedure, criminal procedure)
- Used for importing APK_RF, GPK_RF, UPK_RF codes

### Data Quality

All documents are:
- Sourced from official government websites only
- Hashed for verification
- Timestamped with download date
- Cross-referenced with permanent URLs
- Updated as amendments are published

## Overview

The data pipeline consists of three main stages:

**Quick Start Order** (recommended for first-time users):
```
Step 1: Import Base Codes (import_base_code.py)  → Import 19 core legal codes (~6 hours, ~5,000 articles)
Step 2: Document Sync (initial_sync.py)         → Fetch amendment documents from API (partial: ~6h, full: 100+h)
Step 3: Content + Embeddings (content_sync.py)   → Extract text and generate vectors (~2-3 hours)
```

**Note**: Step 1 (Import Base Codes) is independent and can be run alone to get
the foundational legal codes (~5,000 articles across 19 codes like Civil, Labor, Criminal).
Steps 2-3 add amendment document coverage (partial 2022-2026: ~157k documents in ~6h,
full 2011-present: ~1.6M documents in 100+ hours).

## Prerequisites

```bash
# Start services
cd docker && docker-compose up -d

# Verify services are running
docker-compose ps
# Should show: postgres (5433), qdrant (6333), redis (6380)
```

## Step 2: Document Metadata Sync

Fetches document metadata from pravo.gov.ru and stores in PostgreSQL.

```bash
poetry run python scripts/sync/initial_sync.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

**Options:**
- `--start-date` - First document date to fetch (default: 2020-01-01)
- `--end-date` - Last document date to fetch (default: today)
- `--block` - Filter by publication block (e.g., `president`, `government`, `all`)
- `--batch-size` - Documents per batch (default: 30, API max: 30)
- `--daily` - Run daily sync (yesterday to today)

**Examples:**

```bash
# Sync all documents from 2022 onwards
poetry run python scripts/sync/initial_sync.py --start-date 2022-01-01

# Sync only federal government documents
poetry run python scripts/sync/initial_sync.py --block government

# Daily sync (for cron/scheduler)
poetry run python scripts/sync/initial_sync.py --daily
```

**Current Status:**
- ✅ 157,730 documents synced (2022-2026)
- ⚠️ Date range filtering has issues - see TODO.md
- ⚠️ Full sync would take 100+ hours (1.6M documents total)

## Step 3: Content Parsing + Embeddings

Extracts document text from API metadata and generates embeddings for semantic search.

### Quick Start (Recommended)

```bash
# Parse content AND generate embeddings in one pass
poetry run python scripts/sync/content_sync.py --recreate-collection
```

**Estimated time for 156k documents:**
- Content parsing: 30-60 minutes
- Embeddings (RTX 3060): 1-2 hours
- Total: ~2-3 hours

### Advanced Options

```bash
# Test with 100 documents first
poetry run python scripts/sync/content_sync.py --limit 100 --recreate-collection

# Only parse content (skip embeddings) - for testing
poetry run python scripts/sync/content_sync.py --skip-embeddings

# Only generate embeddings from existing content (resume mode)
poetry run python scripts/sync/content_sync.py --skip-content --recreate-collection
```

**All Options:**
| Option | Purpose |
|--------|---------|
| `--limit N` | Process only N documents (testing) |
| `--skip-content` | Skip parsing, use existing content |
| `--skip-embeddings` | Skip embedding generation |
| `--recreate-collection` | Clear Qdrant and start fresh |

### What the Script Does

1. **Fetches documents** from PostgreSQL (by publish_date DESC)
2. **Parses content** from API metadata (title, name, complexName)
3. **Stores content** in `document_content` table
4. **Generates embeddings** using deepvk/USER2-base (GPU-accelerated)
5. **Stores vectors** in Qdrant for semantic search
6. **Automatic cleanup** - memory management, GPU cache clearing

### Memory Management

The script includes automatic memory cleanup:
- Clears embedding cache after each document
- Forces garbage collection every 50 documents
- Clears CUDA cache (if using GPU)
- Logs memory usage throughout

**Expected memory usage:**
- Model loading: ~500MB (CPU) / ~800MB (GPU)
- Per document: ~10-50MB spikes during processing
- Peaks around 2-3GB with RTX 3060

### Monitoring Progress

```bash
# Watch the logs
poetry run python scripts/sync/content_sync.py --recreate-collection

# You'll see output like:
# [DOC 1/156000] Постановление Правительства... (0 chars, type: xxx)
# [DOC 2/156000] Указ Президента... (0 chars, type: xxx)
# ...
# [MEMORY] After 0 documents: 1234.5 MB
# Batch complete. Total chunks: 1234
```

### Checking Results

```bash
# Check content in database
docker exec law7-postgres psql -U law7 -d law7 -c "
SELECT
  COUNT(*) as total,
  COUNT(full_text) as with_content
FROM document_content;
"

# Check Qdrant collection
curl http://localhost:6333/collections/law_chunks
```

## Step 1: Import Base Legal Codes (Quick Start - Do This First!)

> **Quick Start**: Run this first to get the 19 core legal codes that most users
> need (Civil Code, Labor Code, Criminal Code, etc.). This is completely independent
> from the document sync steps below.

```bash
# List all available codes
poetry run python scripts/import/import_base_code.py --list

# Import all codes
poetry run python scripts/import/import_base_code.py --all

# Import specific code
poetry run python scripts/import/import_base_code.py --code GK_RF
```

**Independence Note**: This step is completely independent from Steps 2-3.
It can be run anytime, even in parallel.

---

Imports the foundational Russian legal codes from official sources.

**Available codes:**

| Code | Name (Russian) | Name (English) | kremlin.ru | pravo.gov.ru | government.ru |
|------|----------------|----------------|------------|--------------|---------------|
| KONST_RF | Конституция Российской Федерации | Constitution | ✅ | ✅ | - |
| GK_RF | Гражданский кодекс | Civil Code Part 1 | ✅ | ✅ | - |
| GK_RF_2 | Гражданский кодекс ч.2 | Civil Code Part 2 | ✅ | ✅ | - |
| GK_RF_3 | Гражданский кодекс ч.3 | Civil Code Part 3 | ✅ | ✅ | - |
| GK_RF_4 | Гражданский кодекс ч.4 | Civil Code Part 4 | ✅ | ✅ | - |
| UK_RF | Уголовный кодекс | Criminal Code | ✅ | ✅ | - |
| TK_RF | Трудовой кодекс | Labor Code | ✅ | ✅ | - |
| NK_RF | Налоговый кодекс | Tax Code Part 1 | ✅ | ✅ | ✅ |
| NK_RF_2 | Налоговый кодекс ч.2 | Tax Code Part 2 | ✅ | ✅ | ✅ |
| KoAP_RF | Кодекс об административных правонарушениях | Administrative Code | ✅ | ✅ | ✅ |
| SK_RF | Семейный кодекс | Family Code | ✅ | ✅ | - |
| ZhK_RF | Жилищный кодекс | Housing Code | ✅ | ✅ | - |
| ZK_RF | Земельный кодекс | Land Code | ✅ | ✅ | ✅ |
| APK_RF | Арбитражный процессуальный кодекс | Arbitration Procedure Code | ✅ | - | ✅ |
| GPK_RF | Гражданский процессуальный кодекс | Civil Procedure Code | ✅ | - | ✅ |
| UPK_RF | Уголовно-процессуальный кодекс | Criminal Procedure Code | ✅ | - | ✅ |
| BK_RF | Бюджетный кодекс | Budget Code | - | - | ✅ |
| GRK_RF | Градостроительный кодекс | Urban Planning Code | - | - | ✅ |
| UIK_RF | Уголовно-исполнительный кодекс | Criminal Executive Code | - | - | ✅ |
| VZK_RF | Воздушный кодекс | Air Code | - | - | ✅ |
| VDK_RF | Водный кодекс | Water Code | - | - | ✅ |
| LK_RF | Лесной кодекс | Forest Code | - | - | ✅ |
| KAS_RF | Кодекс административного судопроизводства | Administrative Procedure Code | ✅ | - | - |

**Import System Features:**
- Automatic source fallback (kremlin → pravo → government)
- Context-based article number validation for fractional articles
- Quality checking to detect source formatting errors
- Hybrid validation using surrounding articles and known ranges

**Current Status:**
- ✅ All 19 codes (23 code identifiers) imported
- ✅ 5,000+ articles total across all codes
- ✅ Metadata stored in `consolidated_codes` table
- ✅ Article validation with context-aware correction

## Verification

### MCP Tools Testing

```bash
# Build and test MCP server
npm run build
npx @modelcontextprotocol/inspector node dist/index.js
```

**Test queries in MCP Inspector:**

1. **List all codes:**
   ```json
   {"name": "get-code-structure"}
   ```

2. **Get specific code structure:**
   ```json
   {
     "name": "get-code-structure",
     "arguments": {"code_id": "TK_RF", "include_articles": true, "article_limit": 10}
   }
   ```

3. **Get specific article:**
   ```json
   {
     "name": "get-article-version",
     "arguments": {"code_id": "TK_RF", "article_number": "80"}
   }
   ```

4. **Search laws:**
   ```json
   {
     "name": "query-laws",
     "arguments": {"query": "трудовой договор", "limit": 5}
   }
   ```

5. **Get statistics:**
   ```json
   {"name": "get-statistics"}
   ```

### Database Statistics

```bash
# Document counts by year
docker exec law7-postgres psql -U law7 -d law7 -c "
SELECT
  EXTRACT(YEAR FROM publish_date) as year,
  COUNT(*) as count
FROM documents
GROUP BY EXTRACT(YEAR FROM publish_date)
ORDER BY year DESC;
"

# Content coverage
docker exec law7-postgres psql -U law7 -d law7 -c "
SELECT
  COUNT(*) as total_documents,
  COUNT(dc.full_text) as with_content,
  COUNT(dc.full_text) * 100.0 / COUNT(*) as coverage_percent
FROM documents d
LEFT JOIN document_content dc ON d.id = dc.document_id;
"

# Code article counts
docker exec law7-postgres psql -U law7 -d law7 -c "
SELECT
  code_id,
  COUNT(*) as articles,
  COUNT(*) FILTER (WHERE is_current = true) as current,
  COUNT(*) FILTER (WHERE is_repealed = true) as repealed
FROM code_article_versions
GROUP BY code_id
ORDER BY code_id;
"
```

## Troubleshooting

### Issue: "value too long for type character varying(1000)"
**Fix:** Already fixed - `documents.name` is now TEXT type

### Issue: "CUDA out of memory"
**Solutions:**
- Reduce `EMBEDDING_BATCH_SIZE` in `.env` (default: 32)
- Close other GPU applications
- Use CPU: set `EMBEDDING_DEVICE=cpu` in `.env`

### Issue: "Connection refused" errors
**Fix:** Ensure Docker services are running:
```bash
cd docker && docker-compose up -d
```

### Issue: Content parsing returns empty strings
**Check:** API metadata structure - some documents only have titles
**Solution:** The parser uses `title || name || complexName` fallback

## Maintenance

### Daily Sync (Recommended)

Set up a cron job to sync new documents daily:

```bash
# Add to crontab (crontab -e)
0 2 * * * cd /path/to/law7 && poetry run python scripts/sync/initial_sync.py --daily
```

### Regenerate Embeddings

If you update the embedding model:

```bash
poetry run python scripts/sync/content_sync.py --recreate-collection
```

### Backup Database

```bash
# Backup PostgreSQL
docker exec law7-postgres pg_dump -U law7 law7 > backup.sql

# Restore
docker exec -i law7-postgres psql -U law7 law7 < backup.sql
```

## Performance Tips

1. **Use GPU for embeddings** - 10x faster than CPU
2. **Batch size**: 30 is API max, don't increase
3. **Embedding batch size**: 32 works well for RTX 3060 12GB
4. **Skip documents >100KB** - Automatically skipped to prevent timeouts
5. **Memory monitoring** - Script logs usage every 50 docs

## File Reference

| Script | Purpose |
|--------|---------|
| `scripts/sync/initial_sync.py` | Fetch document metadata |
| `scripts/sync/content_sync.py` | Parse content + generate embeddings |
| `scripts/sync/fetch_amendment_content.py` | Fetch detailed amendment text |
| `scripts/import/import_base_code.py` | Import base legal codes |
| `scripts/crawler/pravo_api_client.py` | API client for pravo.gov.ru |
| `scripts/parser/html_parser.py` | Parse content from API metadata |
| `scripts/indexer/embeddings.py` | Generate embeddings with deepvk/USER2-base |
| `scripts/indexer/qdrant_indexer.py` | Store embeddings in Qdrant |
