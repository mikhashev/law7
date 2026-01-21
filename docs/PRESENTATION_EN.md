# Law7
## Open Legal Document Database for AI Assistants

---

*Phase 1 - Russia (Operational) | License: AGPL-3.0*

---

## The Problem

AI assistants struggle with legal questions:

- Rely on **outdated training data**
- **Hallucinate** non-existent legal articles
- Give **generic answers** without specific citations
- Cannot track **legal changes over time**

---

## The Solution - Law7

**Mission**: Create an open, global, decentralized database of legal documents

**Key Features**:
- Data **only from official government sources**
- **Full version history** of legal articles (from 2011)
- AI integration via **MCP protocol** (Model Context Protocol)
- **Semantic search** across document content

---

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐    ┌──────────────┐
│ Python Pipeline │ -> │ PostgreSQL +     │ -> │ TypeScript  │ -> │ AI           │
│                 │    │ Qdrant + Redis   │    │ MCP Server  │    │ Assistants   │
└─────────────────┘    └──────────────────┘    └─────────────┘    └──────────────┘
```

**Components**:
- **Data Pipeline** (Python): Crawler, PDF/HTML parser, embeddings generator
- **Databases**: PostgreSQL (metadata), Qdrant (vector search), Redis (cache)
- **MCP Server** (TypeScript): 7 query tools for AI assistants

---

## Current Status - Russia

| Metric | Value |
|--------|-------|
| Documents (2022-2026) | 157,730 |
| Historical (2011-present) | ~1.6M |
| Consolidated Codes | 23 |
| Articles Across Codes | ~6,700 |
| Official Sources | 3 |

**Supported Russian Codes**: Constitution, Civil (4 parts), Criminal, Labor, Tax (2 parts), Family, Housing, Land, Administrative, Procedure codes, and more.

---

## MCP Tools (7 available)

| Tool | Description |
|------|-------------|
| `query-laws` | Semantic/keyword search |
| `get-law` | Retrieve document by number |
| `list-countries` | List supported countries |
| `get-statistics` | Database statistics |
| `get-code-structure` | Code structure and hierarchy |
| `get-article-version` | Article version at specific date |
| `trace-amendment-history` | Track amendment history |

---

## Consolidation Engine

Tracks historical versions of legal articles:

- Fetches amendments from official sources
- Parses amendment documents (additions, repeals, modifications)
- Applies amendments to create historical snapshots
- Maintains audit trail in `amendment_applications` table

**Example query**: *"What was article 155 of the Housing Code in 2020?"*

---

## Official Data Sources

**Russia (Currently Supported)**:
- pravo.gov.ru - Official legal information portal
- kremlin.ru - President of Russia website
- government.ru - Government of Russia website

Each document is:
- Hashed for verification
- Timestamped with download date
- Cross-referenced with permanent URL

---

## Add Your Country - We Need You!

**Phase 3: Global Multi-Country Support**

We're building a worldwide legal database. You can help by adding support for your country's legal system.

**Example countries we want to support**:
- 🇺🇸 **USA**: congress.gov, uscode.house.gov
- 🇫🇷 **France**: legifrance.gouv.fr
- 🇩🇪 **Germany**: gesetze-im-internet.de
- 🇧🇷 **Brazil**: planalto.gov.br
- 🇬🇧 **UK**: legislation.gov.uk
- 🇪🇸 **Spain**: boe.es
- 🇮🇹 **Italy**: gazzettaufficiale.it
- 🇯🇵 **Japan**: e-gov.go.jp
- 🇮🇳 **India**: india.gov.in
- **...and many more!**

---

## How to Contribute - Country Adapter Pattern

Adding a new country is straightforward. Implement this interface:

```python
class CountryAdapter:
    def get_official_urls(self) -> List[str]
    def fetch_documents(self, date: date) -> List[Document]
    def parse_document(self, raw: str) -> ParsedDocument
    def calculate_hash(self, document: Document) -> str
    def create_diff(self, old: Document, new: Document) -> Diff
```

### Step-by-Step Guide

1. **Fork the repository**
   ```bash
   git clone https://github.com/your-username/law7.git
   cd law7
   ```

2. **Create a country adapter**
   ```bash
   # Create: scripts/countries/your_country/adapter.py
   ```

3. **Add tests for parsing logic**
   ```bash
   # Create: scripts/countries/your_country/tests/test_adapter.py
   ```

4. **Submit a Pull Request**
   - Include documentation of official sources
   - Show sample parsed documents
   - Demonstrate test coverage

---

## What You'll Need to Know

**For each official source in your country**:

1. **Official URLs** - Identify the government website(s) that publish laws
2. **Document Format** - PDF, HTML, or other formats
3. **Structure** - How laws are organized (codes, articles, sections)
4. **Update Frequency** - How often new laws are published
5. **Version Tracking** - How amendments and changes are documented

**Example - USA**:
- Main source: congress.gov for federal laws
- Additional: uscode.house.gov for U.S. Code
- Format: HTML and XML
- Structure: Titles → Chapters → Sections
- Updates: Daily as Congress passes laws

---

## Tech Stack

**TypeScript (MCP Server)**:
- @modelcontextprotocol/sdk
- pg, @qdrant/js-client-rest, ioredis
- zod

**Python (Data Pipeline)**:
- pandas, sqlalchemy
- beautifulsoup4, pdfplumber
- sentence-transformers (deepvk/USER2-base)
- torch with CUDA support

**Infrastructure**:
- Docker (PostgreSQL:5433, Qdrant:6333, Redis:6380)
- GPU acceleration (NVIDIA RTX 3060)

---

## Future Roadmap

**Phase 2** (In Progress):
- Consolidation Engine for consolidated codes
- Content importer for all codes
- Testing with real data

**Phase 3** (Planned - Global):
- Multi-country support ← **You can help here!**
- Decentralized storage (IPFS, libp2p)
- Community verification system
- Country adapter framework
- Delta updates and change tracking

---

## ⚠️ Important Notice

**Disclaimer**

- **NOT** for official use in courts or government bodies
- **NO** guarantee of accuracy, completeness, or timeliness
- Always consult qualified lawyers for legal matters
- Data from official sources but may have delays
- AGPL-3.0 license requires sharing modifications

---

## Resources

- **Documentation**: [docs/](docs/)
- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Data Pipeline**: [DATA_PIPELINE.md](DATA_PIPELINE.md)
- **Vision**: [VISION.md](VISION.md)
- **License**: AGPL-3.0

---

## Get Started Today

```bash
# Fork and clone
git clone https://github.com/your-username/law7.git
cd law7

# Install Python dependencies
poetry install

# Install Node dependencies
npm install

# Start Docker services
cd docker && docker-compose up -d

# Run tests
poetry run pytest
npm test
```

**Questions? Open an issue or start a discussion!**

---

*Law7 — Making law accessible to AI, worldwide*
