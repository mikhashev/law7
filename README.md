# Law7

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

> **Note**: Default ports are PostgreSQL **5433**, Redis **6380**, Qdrant **6333** (to avoid conflicts with ygbis).

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

#### Quick Start:
```bash
# Build the server
npm run build

# Add to Claude Desktop
claude mcp add law7 --node c:\Users\mike\Documents\law7\dist\index.js
```

#### Detailed Instructions:

**Step 1: Build and Test the Server**
```bash
npm run build
npm start
```

**Step 2: Add to Claude Desktop**

**Option A: Via Claude Desktop UI:**
1. Open Claude Desktop
2. Go to **Settings** → **MCP Servers**
3. Click **Add MCP Server**
4. Enter:
   - **Name**: `law7`
   - **Command**: `node c:\Users\mike\Documents\law7\dist\index.js`
5. Click **Add**

**Option B: Via Claude Desktop config** (`C:\Users\<user>\.claude\config.json`):
```json
{
  "mcpServers": [
    {
      "name": "law7",
      "command": "node c:\\Users\\mike\\Documents\\law7\\dist\\index.js"
    }
  ]
}
```

**Step 3: Test with Claude Desktop**

Once added, the law7 MCP server should appear in your chat with these tools:
- `list-countries` - List available countries
- `get-statistics` - Get database statistics
- `query-laws` - Search legal documents by text
- `get-law` - Get specific document by eo_number

**Example query:**
```
Can you search for documents about "трудовой договор" in Russia and show me the results?
```

**Troubleshooting:**
- Ensure the server is running before adding to Claude Desktop
- Check Claude Desktop logs for connection errors
- Verify the path uses double backslashes (Windows)

## Project Structure

```
law7/
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
- `sentence-transformers` - Embeddings (deepvk/USER2-base)
- `qdrant-client` - Vector DB client
- `torch` - PyTorch with CUDA support (for GPU acceleration)

**Hardware Requirements for GPU Acceleration:**
- NVIDIA GPU with CUDA support (tested on RTX 3060 12GB)
- CUDA 12.x compatible drivers

## License

MIT
