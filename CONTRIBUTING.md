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
