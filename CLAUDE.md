# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Law7 is a legal document system that uses a **hybrid architecture**:
- **Data Pipeline (Python)** in `/scripts` - Crawls pravo.gov.ru, parses PDFs/HTML, generates embeddings
- **MCP Server (TypeScript)** in `/src` - Serves legal document queries to AI assistants via MCP protocol

```
Python Pipeline → PostgreSQL + Qdrant + Redis → TypeScript MCP Server → AI Assistants
```

## Development Commands

### TypeScript (MCP Server)
```bash
npm run build          # Compile TypeScript
npm run dev            # Build and start server
npm start              # Start compiled server
npx @modelcontextprotocol/inspector node dist/index.js  # Test MCP tools
```

### Python (Data Pipeline)
```bash
poetry install                    # Install dependencies
poetry run python scripts/sync/initial_sync.py        # Initial data import
poetry run python scripts/sync/content_sync.py        # Sync document content + embeddings
poetry run python scripts/import/import_base_code.py  # Import base legal codes
poetry run black scripts/         # Format Python code (line-length: 100)
poetry run ruff check scripts/    # Lint Python code
poetry run pytest scripts/        # Run tests
```

**See [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) for complete data pipeline instructions.**

### Docker Services
```bash
cd docker && docker-compose up -d    # Start PostgreSQL (5433), Qdrant (6333), Redis (6380)
docker-compose logs -f postgres       # View logs
docker-compose down                   # Stop services
```

**Note**: Non-default ports are used to avoid conflicts with other containers: PostgreSQL **5433**, Redis **6380**, Qdrant **6333**.

## Installation

### Prerequisites
- Python 3.10+ with [Poetry](https://python-poetry.org/)
- Node.js 18+ with npm
- Docker & Docker Compose

### Windows Setup

```bash
# Install Poetry (if not already installed)
pip install poetry

# Start Docker services
cd docker
docker-compose up -d

# Install Python dependencies
poetry install

# Install Node dependencies
npm install

# Build and run
npm run build
npm start
```

### macOS/Linux Setup

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Start Docker services
cd docker
docker-compose up -d

# Install dependencies
poetry install
npm install

# Build and run
npm run build
npm start
```

### Verify Installation

```bash
# Test Docker services
docker-compose ps

# Test Python environment
poetry run python -c "import scripts.core.db; print('Python OK')"

# Test TypeScript build
npm run build
```

## Architecture

### TypeScript MCP Server (`/src`)

The MCP server exposes 7 tools for AI assistants:

| Tool | Purpose |
|------|---------|
| `query-laws` | Semantic/keyword search for legal documents |
| `get-law` | Retrieve specific document by eo_number |
| `list-countries` | List supported countries (currently Russia) |
| `get-statistics` | Get database statistics |
| `get-code-structure` | Get structure of consolidated legal codes |
| `get-article-version` | Get article version at specific date |
| `trace-amendment-history` | Track amendment history of articles |

Key files:
- `src/index.ts` - MCP server entry point
- `src/server.ts` - MCP server setup with tool registration
- `src/config.ts` - Configuration (reads from .env)
- `src/db/` - Database clients (PostgreSQL, Qdrant, Redis)
- `src/tools/` - Individual MCP tool implementations
- `src/models/` - TypeScript interfaces for data models

### Python Data Pipeline (`/scripts`)

Core modules:
- `scripts/core/` - Config, database client, batch saver
- `scripts/crawler/` - pravo.gov.ru API client
- `scripts/parser/` - PDF/HTML parsing (`html_parser.py`, `html_scraper.py`)
- `scripts/indexer/` - Embeddings generation, Qdrant/PostgreSQL indexing
- `scripts/consolidation/` - Code consolidation engine for tracking article versions
- `scripts/sync/` - Sync scripts (initial sync, content sync, amendment fetching)
- `scripts/import/` - Base legal code import from official sources
- `scripts/utils/` - Retry logic, progress tracking

### Consolidation Engine

The consolidation system (`scripts/consolidation/`) tracks historical versions of legal articles:
- Fetches amendments from pravo.gov.ru
- Parses amendment documents ( additions, repeals, modifications)
- Applies amendments to create historical snapshots
- Maintains audit trail in `amendment_applications` table
- Supports querying article versions at specific dates

### Database Schema

**PostgreSQL** (`docker/postgres/init.sql`):
- `countries` - Multi-country support (currently Russia)
- `documents` - Main legal documents metadata
- `document_content` - Extracted text content
- `document_chunks` - Text chunks for embeddings
- `code_article_versions` - Historical article snapshots
- `amendment_applications` - Consolidation audit log
- `document_types`, `signatory_authorities`, `publication_blocks`, `categories` - Reference tables

**Qdrant**: Stores 768-dimensional embeddings using deepvk/USER2-base model

**Redis**: Caching layer for API responses and search results

## Key Dependencies

### TypeScript
- `@modelcontextprotocol/sdk` - MCP protocol implementation
- `pg` - PostgreSQL client
- `@qdrant/js-client-rest` - Vector DB client
- `ioredis` - Redis client
- `zod` - Schema validation

### Python
- `pandas` - Data processing
- `sqlalchemy` - Database ORM
- `beautifulsoup4` - HTML parsing
- `pdfplumber` - PDF text extraction
- `sentence-transformers` - Embeddings (deepvk/USER2-base model)
- `torch` - PyTorch with CUDA support for GPU acceleration
- `qdrant-client` - Vector DB client

## Configuration

Environment variables (see `.env.example`):
- Database connection settings (ports 5433, 6380, 6333)
- Embeddings model path
- Batch sizes and retry policies
- GPU/CUDA settings for embeddings

## Code Style

- **TypeScript**: Strict mode enabled
- **Python**: Black formatter (line-length 100), Ruff linter
- **Commits**: Conventional Commits format
- **Tests**: Located in `/scripts`, use pytest

## Development Notes

1. **GPU Acceleration**: The embeddings system uses CUDA for RTX 3060. Falls back to CPU if unavailable.
2. **Port Conflicts**: Services use non-default ports to avoid conflicts with ygbis project.
3. **Hybrid Search**: Combines semantic search (Qdrant) with keyword search (PostgreSQL trigrams).
4. **Official Sources**: All Russian legal data comes from pravo.gov.ru official API.
5. **Historical Tracking**: The consolidation engine maintains full version history of legal articles from 2011-present.

## Two-Phase Development

**Phase 1 (Current)**: Russia-only implementation with centralized architecture.
- 157,730 documents from official Russian sources
- MCP server for chat-based AI assistants (Claude, ChatGPT, Grok)

**Phase 2 (Planned)**: Global multi-country support with decentralized architecture.
- See [docs/VISION.md](docs/VISION.md) for detailed future plans
- Country adapter pattern for adding new jurisdictions
- Community verification and distributed data sharing

## Supported Legal Codes (Phase 1 - Russia)

The system currently supports **19 consolidated Russian legal codes**:

| Code ID | Name (Russian) | Name (English) | Source |
|---------|----------------|----------------|--------|
| KONST_RF | Конституция Российской Федерации | Constitution | kremlin.ru |
| GK_RF | Гражданский кодекс | Civil Code Part 1 | pravo.gov.ru |
| GK_RF_2 | Гражданский кодекс ч.2 | Civil Code Part 2 | pravo.gov.ru |
| GK_RF_3 | Гражданский кодекс ч.3 | Civil Code Part 3 | pravo.gov.ru |
| GK_RF_4 | Гражданский кодекс ч.4 | Civil Code Part 4 | pravo.gov.ru |
| UK_RF | Уголовный кодекс | Criminal Code | pravo.gov.ru |
| TK_RF | Трудовой кодекс | Labor Code | pravo.gov.ru |
| NK_RF | Налоговый кодекс | Tax Code Part 1 | pravo.gov.ru |
| NK_RF_2 | Налоговый кодекс ч.2 | Tax Code Part 2 | pravo.gov.ru |
| KoAP_RF | Кодекс об административных правонарушениях | Administrative Code | pravo.gov.ru |
| SK_RF | Семейный кодекс | Family Code | pravo.gov.ru |
| ZhK_RF | Жилищный кодекс | Housing Code | pravo.gov.ru |
| ZK_RF | Земельный кодекс | Land Code | pravo.gov.ru |
| APK_RF | Арбитражный процессуальный кодекс | Arbitration Procedure Code | government.ru |
| GPK_RF | Гражданский процессуальный кодекс | Civil Procedure Code | government.ru |
| UPK_RF | Уголовно-процессуальный кодекс | Criminal Procedure Code | government.ru |
| BK_RF | Бюджетный кодекс | Budget Code | government.ru |
| GRK_RF | Градостроительный кодекс | Urban Planning Code | government.ru |
| UIK_RF | Уголовно-исполнительный кодекс | Criminal Executive Code | government.ru |
| VZK_RF | Воздушный кодекс | Air Code | government.ru |
| VDK_RF | Водный кодекс | Water Code | government.ru |
| LK_RF | Лесной кодекс | Forest Code | government.ru |
| KAS_RF | Кодекс административного судопроизводства | Administrative Procedure Code | kremlin.ru |

**Total**: 23 code identifiers (19 unique codes, some split into parts)

## When to Update CLAUDE.md

Update this file when:
- Adding new MCP tools or changing existing tool interfaces
- Significant architecture changes (new services, data flow changes)
- New code sources or countries added to the pipeline
- Breaking changes to APIs or data pipeline
- New consolidated legal codes imported
- Installation or setup procedures change
