# Laws-Context7

An MCP (Model Context Protocol) server for querying legal documents from multiple countries, starting with the Russian Federation.

## Architecture

This project uses a **hybrid architecture** with two separate components:

- **Data Pipeline (Python)**: Crawls, parses, and indexes legal documents into local database
- **MCP Server (TypeScript)**: Queries the local database and serves results to AI assistants

```
Python Pipeline → PostgreSQL + Qdrant → TypeScript MCP Server → AI
```

## Components

| Component | Language | Location | Status |
|-----------|----------|----------|--------|
| Data Pipeline | Python | `/scripts` | Private |
| MCP Server | TypeScript | `/src` | Public |
| Docker | Compose | `/docker` | Public |

## Quick Start

### 1. Start Docker Services

```bash
cd docker
docker-compose up -d
```

### 2. Run Initial Data Sync (Python)

```bash
# Using Poetry
poetry run python scripts/sync/initial_sync.py
```

### 3. Start MCP Server (TypeScript)

```bash
npm install
npm run build
npm start
```

### 4. Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

### 5. Add to Claude Code

```bash
claude mcp add laws-context7 -- node c:\Users\mike\Documents\laws-context7\dist\index.js
```

## Project Structure

```
laws-context7/
├── src/                     # TypeScript - MCP Server (PUBLIC)
│   ├── index.ts             # MCP server entry point
│   ├── server.ts            # MCP server setup
│   ├── config.ts            # Configuration
│   ├── tools/               # MCP tools
│   ├── db/                  # Database clients
│   └── models/              # Data models
│
├── scripts/                 # Python - Data Pipeline (PRIVATE)
│   ├── core/                # Core utilities (config, db, batch_saver)
│   ├── crawler/             # Pravo.gov.ru API crawler
│   ├── parser/              # PDF/HTML parsing
│   ├── indexer/             # Embeddings and indexing
│   └── sync/                # Sync scripts (initial, daily)
│
└── docker/                  # Docker services
    ├── docker-compose.yml   # PostgreSQL, Qdrant, Redis
    └── postgres/
        └── init.sql         # Database schema
```

## MCP Tools

- `resolve-country` - Resolve country name to country ID
- `resolve-law-category` - Find legal category (e.g., Labor Code)
- `query-laws` - Search local database for relevant laws
- `get-document-full-text` - Get full document text

## Data Source

The Russian legal data is sourced from the official [pravo.gov.ru](http://pravo.gov.ru/) API.

## Dependencies

### TypeScript (MCP Server)
- `@modelcontextprotocol/sdk` - MCP protocol
- `pg` - PostgreSQL client
- `@qdrant/js-client-rest` - Qdrant vector DB client
- `ioredis` - Redis client

### Python (Data Pipeline)
- `pandas` - Data processing
- `sqlalchemy` - Database ORM
- `beautifulsoup4` - HTML parsing
- `pdfplumber` - PDF text extraction
- `sentence-transformers` - Embeddings
- `qdrant-client` - Vector DB client

## License

MIT
