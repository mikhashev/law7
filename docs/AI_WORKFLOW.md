# AI-Assisted Development Guidelines

This document provides guidelines for using AI assistants (Claude Code, Cursor, etc.) when working on the Law7 project.

## Dependency Management Rules

**CRITICAL**: Always use `poetry` for Python dependency management, never `pip` directly.

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

## Getting Context with Git

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
5. Understand what branch you're on (main vs feature branch)

## Database Schema Verification with AI

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

## API Research with AI

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
- [docs/ROADMAP.md](ROADMAP.md) - Project priorities and implementation status
- [scripts/docs/pravo_api_analysis.md](scripts/docs/pravo_api_analysis.md) - pravo.gov.ru API documentation

## Recommended MCP Servers

| MCP Server | Purpose |
|------------|---------|
| **Context7** | Library documentation lookup |
| **Filesystem** | File operations |
| **Postgres** | Direct database queries during development |
| **Brave Search** | Research legal APIs and data sources |

## Development Workflow with AI

When developing with AI assistants (Claude Code, Cursor):

1. **Use Context7** for library-specific questions:
   - "How do I use pg with connection pooling?" → Check Context7 for `pg` docs
   - "Sentence transformers batch processing" → Check Context7

2. **Reference patterns** from your other projects:
   - Exponential backoff retry pattern
   - Batch upsert with SQLAlchemy
   - Context manager database connections
   - Docker health check patterns

3. **Test MCP tools locally**:
   ```bash
   npx @modelcontextprotocol/inspector node dist/index.js
   ```

## Example Workflow

```bash
# 1. Check current state
git status
# Output: Shows modified/new files, current branch

# 2. Understand recent work
git log --oneline -10
# Output: Shows recent commits

# 3. Check specific file history
git log --oneline -- scripts/parser/html_scraper.py
# Output: Shows evolution of the file

# 4. Check database schema before querying
docker exec law7-postgres psql -U law7 -d law7 -c "\d code_article_versions"
# Output: Shows actual columns, types, and constraints

# 5. Now make informed changes
```

## AI Assistant Context Rules

When working with this codebase via AI assistants:

1. **Always read files before editing** - Never make assumptions about file contents
2. **Check git status** before suggesting changes
3. **Verify database schema** before writing queries
4. **Test commands** before suggesting them to users
5. **Preserve existing patterns** - Follow the project's coding conventions
6. **Ask for clarification** when requirements are ambiguous

## Project-Specific Considerations

### Legal Data Handling
- All data must come from official government sources (pravo.gov.ru, kremlin.ru, government.ru)
- Never use commercial sources (consultant.ru, garant.ru) without proper licensing
- Document the source of all imported data
- Verify data integrity with hash checks

### Consolidation Engine
- The consolidation system tracks historical versions of legal articles
- Amendments must be applied in chronological order
- Each article version must be stored with its effective date
- The amendment_applications table provides an audit trail

### MCP Tool Development
- Tools must handle both semantic and keyword search
- All tools should validate input parameters
- Error messages must be user-friendly
- Tools should return structured, parseable output

## Getting Started with AI Development

1. **Read the project documentation**: Start with [README.md](../README.md) and [docs/DATA_PIPELINE.md](DATA_PIPELINE.md)
2. **Set up your environment**: Follow the installation instructions
3. **Explore the codebase**: Use glob patterns to find relevant files
4. **Understand the data model**: Check `docker/postgres/init.sql` for schema
5. **Test your changes**: Always test before committing

## Need Help?

- Open an issue for questions
- Check existing issues for similar discussions
- Review [docs/](docs/) for additional documentation
- Reference [CONTRIBUTING.md](../CONTRIBUTING.md) for general contribution guidelines
