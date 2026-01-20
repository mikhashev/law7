# Contributing to Law7

## Commit Conventions

This project uses **Conventional Commits** for all commit messages.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code refactoring (no functional change) |
| `docs` | Documentation changes |
| `test` | Test additions or changes |
| `chore` | Build, tooling, dependency updates |
| `perf` | Performance improvements |
| `style` | Code style changes (formatting, etc.) |

### Examples

```
feat(db): add connection pooling for PostgreSQL
fix(crawler): handle rate limiting errors from pravo.gov.ru
refactor(tools): extract common validation logic
docs(readme): update installation instructions
test(indexer): add unit tests for chunker module
chore(deps): upgrade sentence-transformers to v3.3.1
```

### Guidelines

- Use lowercase for type and scope
- Keep description under 72 characters
- Use imperative mood ("add" not "added" or "adds")
- **No emojis anywhere** in the project (code, docs, commits, etc.)
- Include scope when relevant (db, crawler, parser, indexer, tools, etc.)
- Reference issues in footer: `Closes #123`

## Development Setup

See [README.md](README.md) for setup instructions.

### Dependency Management Rules

**CRITICAL**: Always use `poetry` for dependency management, never `pip` directly.

```bash
# ✅ CORRECT - Use Poetry
poetry add package-name
poetry run pip install package-name
poetry install

# ❌ WRONG - Never use pip directly outside of Poetry
pip install package-name
python -m pip install package-name
```

**Why?** This project uses Poetry for dependency management. Installing packages with `pip` directly bypasses Poetry's virtual environment and can cause version conflicts.

**Special case for PyTorch with CUDA support**:
```bash
# For CUDA-enabled PyTorch, use Poetry's pip wrapper:
poetry run pip uninstall torch -y
poetry run pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## AI Assistant Tools

This project is designed to work with AI assistants and MCP (Model Context Protocol) tools.

### Context7 (Documentation Lookup)

Use [Context7](https://github.com/upstash/context7) for quick access to library documentation:

```bash
# Context7 is available as an MCP server
# Add it to Claude Code or Cursor for inline docs
```

**Useful Context7 libraries for this project:**
- `/vercel/next.js` - For potential future web UI
- `/mongodb/docs` - Documentation patterns
- `/supabase/supabase` - Database patterns
- Any library in `package.json` or `pyproject.toml`

### Recommended MCP Servers

| MCP Server | Purpose |
|------------|---------|
| **Context7** | Library documentation lookup |
| **Filesystem** | File operations |
| **Postgres** | Direct database queries during development |
| **Brave Search** | Research legal APIs and data sources |

### Development Workflow with AI

When developing with AI assistants (Claude Code, Cursor):

1. **Use Context7** for library-specific questions:
   - "How do I use pg with connection pooling?" → Check Context7 for `pg` docs
   - "Sentence transformers batch processing" → Check Context7

2. **Reference ygbis patterns** from `C:\Users\mike\Documents\yandex-games-bi-suite`:
   - Exponential backoff retry pattern
   - Batch upsert with SQLAlchemy
   - Context manager database connections
   - Docker health check patterns

3. **Test MCP tools locally**:
   ```bash
   npx @modelcontextprotocol/inspector node dist/index.js
   ```

### Getting Context with Git

**CRITICAL**: Before making any changes, AI assistants MUST check git history for context.

```bash
# Always check git status first
git status

# Review recent commit messages to understand patterns
git log --oneline -20

# See what changed in specific files
git log --oneline -- <path-to-file>

# View recent changes for context
git diff HEAD~5
```

**Why?** Git history provides critical context:
- **Recent changes** show what was just worked on
- **Commit patterns** reveal project conventions (scopes, types)
- **File history** indicates ownership and dependencies
- **Uncommitted changes** show work in progress

**Best practices for AI assistants**:
1. Always check `git status` at the start of a session
2. Review recent commits before suggesting changes
3. Look at commit message patterns to match the project style
4. Check if files are modified/deleted/added before editing them
5. Understand what branch you're on (master vs feature branch)

**Example workflow**:
```bash
# 1. Check current state
git status
# Output: Shows modified/new files, current branch

# 2. Understand recent work
git log --oneline -10
# Output: Shows recent commits like "feat(parser): add technical metadata filtering"

# 3. Check specific file history
git log --oneline -- scripts/parser/html_scraper.py
# Output: Shows evolution of the file

# 4. Now make informed changes
```

### Database Schema Verification with AI

**CRITICAL**: Before making any database changes, AI assistants MUST check the actual database schema.

```bash
# Check the real database schema
docker exec law7-postgres psql -U law7 -d law7 -c "\d table_name"

# List all tables
docker exec law7-postgres psql -U law7 -d law7 -c "\dt"

# View table structure with column types
docker exec law7-postgres psql -U law7 -d law7 -c "\d+ table_name"

# Check indexes
docker exec law7-postgres psql -U law7 -d law7 -c "\di"

# View specific constraints
docker exec law7-postgres psql -U law7 -d law7 -c "
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'table_name'
    ORDER BY ordinal_position;
"
```

**Why?** Assumptions about database schema can lead to errors:
- **Column names** may differ from expectations (snake_case vs camelCase)
- **Data types** may be incompatible (text vs varchar, integer vs bigint)
- **Constraints** may exist (NOT NULL, UNIQUE, FOREIGN KEY)
- **Indexes** may affect query performance
- **Missing columns** will cause runtime errors

**Best practices for AI assistants**:
1. Always check `\d table_name` before writing INSERT/UPDATE queries
2. Verify column types match the data being inserted
3. Check for required columns (NOT NULL constraints)
4. Look for foreign key relationships before deleting data
5. Test queries with `SELECT` before running `INSERT/UPDATE/DELETE`

**Example workflow**:
```bash
# 1. Check schema before writing query
docker exec law7-postgres psql -U law7 -d law7 -c "\d code_article_versions"
# Output: Shows actual columns, types, and constraints

# 2. Verify data compatibility
docker exec law7-postgres psql -U law7 -d law7 -c "
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'code_article_versions';
"

# 3. Write correct query based on actual schema
# If article_number is varchar(20), don't insert integer
# If version_date is date, don't insert datetime without casting
```

### API Research with AI

When exploring new APIs or data sources:

1. **Use AI to analyze API endpoints**:
   - "Analyze the pravo.gov.ru API endpoints"
   - Reference: [scripts/docs/pravo_api_analysis.md](scripts/docs/pravo_api_analysis.md)

2. **Document findings in analysis docs**:
   - Endpoint URLs and parameters
   - Response structures
   - Rate limits and timeouts
   - Authentication requirements

3. **Update code based on analysis**:
   - Add new API client methods
   - Update database schema for new fields
   - Add error handling for edge cases

**Key References**:
- [TODO.md](TODO.md) - Project priorities and implementation status
- [scripts/docs/pravo_api_analysis.md](scripts/docs/pravo_api_analysis.md) - pravo.gov.ru API documentation

## Project Plans

Strategic planning documents are maintained in `.claude/plans/`:
- [Consolidation Engine Plan](.claude/plans/snuggly-nibbling-lecun.md) - Database consolidation strategy

When implementing major features, reference these plans for:
- Architecture decisions
- Implementation phases
- Success criteria
- Technical trade-offs

## Contributing to Global Expansion

Law7 aims to become a global legal document system. See [docs/VISION.md](docs/VISION.md) for the complete vision.

### Adding a New Country

To add support for a new country, follow these steps:

#### 1. Research Official Sources

Identify the official government legal publication portals for your country:

**Examples**:
- **United States**: congress.gov, uscode.house.gov
- **France**: legifrance.gouv.fr
- **Germany**: gesetze-im-internet.de
- **Brazil**: planalto.gov.br
- **Japan**: e-gov.go.jp

**Requirements**:
- Must be official government sources
- Must provide API or HTML access
- Must have stable, permanent URLs
- Must include document metadata (date, type, number)

#### 2. Create a Country Adapter

Create a new adapter in `scripts/crawler/adapters/<country_code>/`:

```python
# scripts/crawler/adapters/us/country_adapter.py
from scripts.crawler.base_adapter import BaseCountryAdapter

class USCountryAdapter(BaseCountryAdapter):
    def get_official_urls(self) -> List[str]:
        return ["https://congress.gov", "https://uscode.house.gov"]

    def fetch_documents(self, date: date) -> List[Document]:
        # Implementation for fetching documents
        pass

    def parse_document(self, raw: str) -> ParsedDocument:
        # Implementation for parsing documents
        pass

    def calculate_hash(self, document: Document) -> str:
        # Implementation for hashing
        pass
```

#### 3. Add Country to Database

```sql
INSERT INTO countries (code, name, native_name) VALUES
('US', 'United States', 'United States');
```

#### 4. Implement MCP Tools

Update the MCP tools in `src/tools/` to support the new country:
- `query-laws`: Filter by country code
- `get-law`: Handle country-specific document IDs
- `list-countries`: Include new country

#### 5. Add Tests

Create tests for the new adapter:
```python
# scripts/crawler/adapters/us/test_country_adapter.py
def test_fetch_documents():
    adapter = USCountryAdapter()
    documents = adapter.fetch_documents(date(2025, 1, 1))
    assert len(documents) > 0
```

#### 6. Update Documentation

Update the following files:
- `README.md`: Add country to the list
- `docs/DATA_PIPELINE.md`: Document the new adapter
- `CLAUDE.md`: Add country-specific notes

### Contribution Guidelines for Global Expansion

#### Official Sources Only

- Only use official government legal publication portals
- Document the source URLs in code and documentation
- Implement hash verification for all documents

#### Data Quality

- Implement proper parsing for legal document structure
- Handle edge cases (amendments, repeals, consolidation)
- Add tests for parsing logic

#### Community Verification

- Follow the verification pattern from [docs/VISION.md](docs/VISION.md)
- Implement hash-based verification
- Consider contributing verification nodes

#### License Compliance

- All contributions must be AGPL-3.0 compatible
- Respect copyright of legal texts (usually public domain for government works)
- Document any licensing considerations

### Getting Started with Global Contributions

1. **Join the Discussion**: Open an issue to discuss the country you want to add
2. **Research**: Document the official sources and API endpoints
3. **Proposal**: Create a proposal issue with:
   - Country name and code
   - Official sources
   - Document types to import
   - Expected challenges
4. **Implementation**: Follow the country adapter pattern
5. **Testing**: Test with real data from official sources
6. **Documentation**: Update all relevant documentation

### Example: Adding France

```python
# scripts/crawler/adapters/fr/country_adapter.py
from scripts.crawler.base_adapter import BaseCountryAdapter

class FRCountryAdapter(BaseCountryAdapter):
    """Adapter for French legal documents from Legifrance."""

    def get_official_urls(self) -> List[str]:
        return ["https://legifrance.gouv.fr"]

    def fetch_documents(self, date: date) -> List[Document]:
        # Implement using Legifrance API or HTML scraping
        pass
```

### Need Help?

- Open an issue for questions
- Check existing adapters for reference
- Review [docs/VISION.md](docs/VISION.md) for architecture guidance
- Join community discussions

### Recognition

Contributors who add new countries will be:
- Listed in CONTRIBUTORS.md
- Credited in README.md
- Recognized in release notes
