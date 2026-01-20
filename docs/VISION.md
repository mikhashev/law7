# Law7 Phase 2: Global Vision

**Status**: Conceptual / Proof-of-Concept
**Current Phase**: Phase 1 (Russia-only operational)
**License**: AGPL-3.0

## Mission

Create an open, global, decentralized database of legal texts from all countries that:

- Allows anyone to access current legal texts for free and without restrictions
- Can be easily connected to any AI system (local or cloud-based)
- Enables people to discuss laws, solve legal questions, model situations, and verify rights and obligations with AI assistance
- Is open for participation - anyone can add/maintain laws for their country

## Architecture Overview

### 1. Data Sources

**Core Principle**: Official government sources are the only trusted anchor.

Examples by country:
- **Russia**: pravo.gov.ru, kremlin.ru, government.ru
- **United States**: congress.gov, uscode.house.gov
- **France**: legifrance.gouv.fr
- **Germany**: gesetze-im-internet.de, bundesgesetzblatt.de
- **Brazil**: planalto.gov.br

Each country adapter knows its official URL(s) and always cross-references the live version.

### 2. Collection and Updates

Each participant runs their local scraper for one or more jurisdictions:

- Scrapers periodically (daily/hourly/on-trigger) download texts and parse them
- Calculate hash/checksum for each document
- If hash changed: create delta-update (diff) with metadata:
  - Exact URL
  - Download timestamp
  - Full document hash
  - Diff hash

### 3. Data Distribution

**Publication Format**: JSON / JSONL / CSV + markdown diffs

**Storage Options**:
- Public buckets (S3, Cloudflare R2, Backblaze B2)
- IPFS for distributed storage
- Hybrid approach

**Directory Structure**:
```
/data/
  ru/2026-01-20/
  us/2026-01-20/
  br/...
```

**Distribution Methods**:
- IPFS with pubsub
- libp2p gossip protocol
- Simple webhook notifications
- RSS/Atom feeds per country

### 4. Verification

Any node can independently download the original from the specified URL and verify the hash:

- If hash matches: update is valid
- If most nodes confirm: update is accepted

**Two Modes**:

1. **Strict Mode**: Requires exact match with official source
2. **Soft Mode**: Community can vote/sign updates with cryptographic keys (if official site temporarily unavailable)

### 5. Local Cache and AI Integration

**Local Storage**:
- Redis / SQLite / vector DB on user's device

**AI Integration**:
- RAG approach: AI reads current text + diff + context
- Answers questions like:
  - "Can I terminate a rental agreement with 2 months notice in the Netherlands?"
  - "What are the speeding fines in Brazil in 2026?"

## Protection Against Invalid Data

- Official source is always the ground truth
- Hash mismatch: automatic rejection
- Malicious changes quickly filtered by any node's independent verification
- Optional additional protection:
  - GPG / cryptographic signatures from active contributors
  - Reputation system (simpler than git, but similar concept)

## Country Adapter Pattern

To add a new country, implement the following interface:

```python
class CountryAdapter:
    def get_official_urls(self) -> List[str]
    def fetch_documents(self, date: date) -> List[Document]
    def parse_document(self, raw: str) -> ParsedDocument
    def calculate_hash(self, document: Document) -> str
    def create_diff(self, old: Document, new: Document) -> Diff
```

**Examples to Implement**:
- USAdapter: congress.gov, federal register
- FRAdapter: legifrance.gouv.fr
- DEAdapter: gesetze-im-internet.de

## Legal Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md). Key points:

- This is NOT for official use
- No guarantees of accuracy or completeness
- Always consult qualified lawyers
- AGPL-3.0 requires sharing modifications

## Contributing

To add your country:

1. Fork the repository
2. Implement a CountryAdapter for your country's official legal sources
3. Add tests for parsing logic
4. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for commit conventions and development setup.

## Current Status

### Phase 1: Operational (Russia)
- 157,730 documents indexed
- All 16 major Russian legal codes imported
- MCP server with 7 tools functional
- Sources: pravo.gov.ru, kremlin.ru, government.ru

### Phase 2: Planned (Global)
- Multi-country support architecture
- Distributed data distribution (IPFS/libp2p)
- Community verification system
- Country adapter framework
- Delta updates and change tracking

## Resources

- [DATA_PIPELINE.md](DATA_PIPELINE.md) - Current data pipeline documentation
- [DISCLAIMER.md](DISCLAIMER.md) - Legal disclaimer
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines

---

**Note**: This is a forward-looking vision. The current implementation (Phase 1) focuses on Russian legal documents and uses a centralized architecture. Phase 2 represents the planned evolution to a global, decentralized system.
