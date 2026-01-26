# AI-Assisted Development Guidelines

This document provides guidelines for using AI assistants (Claude Code, Cursor, etc.) when working on the Law7 project.

## AI-First Development Philosophy

> **Philosophy Reference**: Our AI-First approach is based on [personal context for AI-human cognitive enhancement](https://github.com/mikhashev/personal-context-manager/blob/main/docs/ultimate%20guide%20on%20personal%20context%20for%20AI-human%20cognitive%20enhancement.md) - using AI to enhance human intelligence rather than replace it.

Law7 is built around **AI-human cognitive partnership** - we use AI assistants to enhance, not replace, our thinking and development capabilities.

### Five Core Principles

1. **Conscious Delegation**
   - Delegate to AI only after understanding the codebase context
   - Check `git status` and `git log` before requesting changes
   - Verify AI suggestions against actual code/database schema

2. **Cognitive Partnership**
   - Use AI as thinking enhancer, not replacement
   - "First self, then AI" - form your own understanding first
   - Use Socratic dialogue with AI to deepen comprehension

3. **Active Thinking**
   - Always explore code structure yourself before delegating to AI
   - Use Explore agent to understand patterns, then synthesize your own understanding
   - Verify AI suggestions match existing codebase conventions

4. **Metacognitive Monitoring**
   - After AI assistance, reflect on what you learned
   - Track which skills you're developing vs. delegating
   - Document new understanding in your own words

5. **Transparent Collaboration**
   - Request AI to explain reasoning, not just provide code
   - Ask for alternatives when implementing features
   - Maintain understanding of all changes you commit

### Practical Workflow

**Before requesting AI assistance:**
```bash
git status                    # What's changed?
git log --oneline -20         # What's the context?
```

**During AI collaboration:**
- Use Explore agent to understand codebase structure
- Request explanations of reasoning, not just solutions
- Ask questions to verify your understanding

**After AI assistance:**
- Review all proposed changes
- Verify against actual schema/patterns
- Commit with your own understanding of the change

### Anti-Bias Awareness

> **AI Bias Awareness**: When working with AI assistants, be aware of cognitive biases in AI systems. See [Cognitive Bias in AI and LLMs: A User's Guide](https://github.com/mikhashev/personal-context-manager/blob/main/docs/cognitive%20bias%20in%20AI%20and%20LLMs%20a%20user's%20guide.md) for practical techniques to recognize and mitigate AI biases.

---

## Plan Mode and Bias Mitigation

When creating implementation plans or architectural decisions, AI assistants must apply **bias mitigation rules** to avoid default patterns and ensure better decision-making.

### Bias Mitigation Rules

**CRITICAL**: AI assistants act as knowledge curators with strong bias-awareness training. Apply these rules during planning:

1. **Challenge Status Quo**
   - Always question existing approaches and assumed sequences
   - Ask: "Is this phase actually necessary? What if we skipped it?"
   - Example: Initially planned Phase 0 (P2P research) before Phase 7 (refactoring), but challenging this revealed Phase 7 should come first

2. **Multi-Cultural Perspective**
   - Consider approaches from at least 3 different cultures/contexts
   - Ask: "How would a startup in Berlin approach this? A research lab in Tokyo? A government agency in Estonia?"
   - Helps escape local/cultural blind spots in solution design

3. **Framing Neutrality**
   - Present multiple options without expressing preference
   - Use neutral language: "Option A, Option B, Option C" not "Recommended, Alternative, Last Resort"
   - Let the human decide after seeing all trade-offs

4. **Evidence-Based Reasoning**
   - Require citations and reasoning for recommendations
   - Ask: "What evidence supports this approach? What are the metrics?"
   - Link to actual data from the codebase, not assumptions

5. **Devil's Advocate**
   - Argue against your initial recommendation
   - Ask: "What's the strongest case against this approach?"
   - Present the best counter-arguments and risks

### Systems Thinking for Planning

When planning phases or architectural changes, apply systems thinking principles:

**1. Fast Feedback Loops**
```
Bad: Phase 0 → Phase 7 → Results (months later)
Good: Phase 7 → Immediate validation → Phase 0 (targeted)
```

**2. Solve Concrete Problems, Not Abstract Ones**
- Before: "Research P2P for unknown requirements"
- After: "Research P2P for DocumentSync interface that we defined"
- Ask: "What's the REAL problem we're solving?"

**3. Reduce Uncertainty**
- Define concrete interfaces before researching implementations
- Measure actual requirements (data volumes, update patterns)
- Make research questions answerable: "Which P2P implements DocumentSync efficiently for X GB daily?"

### Critical Path Analysis

When planning phased work:

1. **Identify the critical path**: Which phases block others?
2. **Separate blocking from supportive**: Some phases are important but not blocking
3. **Present sequencing options**: Sequential, Critical Path First, Parallel

**Example**:
- Critical path: Phase 7 (refactoring) → Phase 0 (P2P) → Phase 4 (multi-country)
- Supportive: Phase 1 (foundation/quality) - important but not blocking
- Options presented: Sequential (safer), Critical Path First (faster), Parallel (fastest)

### Case Study: Phase 0 → Phase 7 Revision

**Initial Plan**: Start with Phase 0 (P2P Research) to inform Phase 7's adapter pattern

**Bias Mitigation Applied**:
1. **Challenge Status Quo**: "Is Phase 0 really needed before Phase 7?"
2. **Devil's Advocate**: Argued against abstract P2P research without concrete requirements
3. **Evidence-Based**: Examined actual user burden (157K documents parsed per user)
4. **Systems Thinking**: Applied fast feedback loops principle

**Revised Plan**: Phase 7 first - define DocumentSync ABC, refactor Russia module, THEN Phase 0 implements DocumentSync with P2P technologies

**Result**: Clear interface definition, concrete requirements for P2P research, faster validation loop

### Plan Mode Workflow

When user requests planning work:

```bash
# 1. Understand the REAL problem
Ask: "What problem are we actually solving? For whom?"

# 2. Check existing plans
Read existing phase documents, roadmap, vision docs

# 3. Apply bias mitigation
- Challenge the assumed approach
- Generate 3+ alternative sequencing options
- Present trade-offs neutrally
- Argue against your own recommendation

# 4. Use systems thinking
- Identify critical path vs supportive work
- Check feedback loop timing
- Reduce uncertainty where possible

# 5. Present options with clear trade-offs
Option 1: [description] | [pros] | [cons] | [when to choose]
Option 2: [description] | [pros] | [cons] | [when to choose]
Option 3: [description] | [pros] | [cons] | [when to choose]
```

### Anti-Patterns to Avoid

| Anti-Pattern | Description | Better Approach |
|--------------|-------------|-----------------|
| **Research First** | Start with abstract research before defining concrete needs | Define interface/requirements, then targeted research |
| **Assumed Sequence** | Follow roadmap phases in order without questioning | Analyze dependencies, identify critical path |
| **Preference Framing** | Present "recommended" option with "alternatives" | Present all options as neutral choices |
| **Status Quo Bias** | "This is how we planned it" without challenging | "Why this phase? What if we skipped it?" |
| **Abstract Problems** | "Research P2P for legal documents" | "Implement DocumentSync ABC for 50MB daily updates" |

---

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

## Before Starting Work

**CRITICAL**: Before starting any task, AI assistants MUST check what's already in progress.

```bash
# Check open issues to see what's being worked on
gh issue list --repo mikhashev/law7 --state open --limit 50

# Or use GitHub MCP to list issues
# Search for issues with "in_progress" status on project board

# Check recent commits to understand current work
git log --oneline -10

# Check git status for uncommitted changes
git status
```

**Why?** This prevents:
- **Duplicate work** - Someone else may already be working on the same issue
- **Conflicting changes** - Multiple AI sessions modifying same files
- **Lost context** - Understanding what was just worked on
- **Breaking changes** - Unaware of in-progress refactoring

**Best practices for AI assistants:**
1. Always check open issues before creating new ones
2. Look for "In Progress" items on the project board
3. Check if files you're about to edit are already modified
4. Comment on existing issues rather than creating duplicates
5. Ask user if task conflicts with in-progress work

**Workflow:**
1. Search for existing issues related to your task
2. If found, comment on the issue or ask to assign it
3. If not found, create new issue following template structure
4. Add issue to project board using appropriate tools

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

## Creating GitHub Issues

When creating GitHub issues, use the templates from `.github/ISSUE_TEMPLATE/` to ensure consistency and completeness.

### Available Templates

| Template | Prefix | Purpose | Labels |
|----------|--------|---------|--------|
| `bug_report.md` | `[BUG]` | Report bugs or unexpected behavior | `bug` |
| `feature_request.md` | `[FEAT]` | Suggest new features or enhancements | `enhancement` |
| `documentation.md` | `[DOCS]` | Request documentation improvements | `documentation` |
| `question.md` | `[QUESTION]` | Ask questions about the project | (none) |

### Using Templates

**Via GitHub CLI** (templates auto-applied):
```bash
gh issue create --repo mikhashev/law7 --template "bug_report.md"
gh issue create --repo mikhashev/law7 --template "feature_request.md"
gh issue create --repo mikhashev/law7 --template "documentation.md"
```

**Via GitHub MCP** (manually follow template structure):
```typescript
// Structure issue body to match the relevant template
// For bug_report.md include:
- Bug Description
- To Reproduce (steps)
- Expected Behavior
- Environment (OS, versions)
- Logs (if applicable)

// For feature_request.md include:
- Feature Description
- Problem Statement
- Proposed Solution
- Alternatives Considered
- Implementation Ideas (optional)
```

### Issue Title Conventions

Match the template prefix style:
- Bugs: `[BUG] Short description` or `bug: short description`
- Features: `[FEAT] Short description` or `feat: short description`
- Docs: `[DOCS] Short description` or `docs: short description`
- Phase tasks: `[Phase X] Short description` or `[Phase X.Y] Short description`

### Phase Task Issues

For phase-based tasks (from roadmap/PHASE*.md files), use structured format:
```markdown
## Task
[Brief description of the task]

## Overview
[Context about why this task matters, which phase it belongs to]

## Requirements
- Requirement 1
- Requirement 2

## Files to Create/Modify
- `path/to/file1` - Description
- `path/to/file2` - Description

## Deliverables
- [ ] Deliverable 1
- [ ] Deliverable 2

## Reference
- Link to relevant PHASE*.md documentation
- Related issues/PRs

## Priority
[CRITICAL/HIGH/MEDIUM/LOW]
```

### Before Creating an Issue

1. **Search for existing issues** - Check if similar work is already tracked
2. **Check project board** - Look for related items in backlog/in-progress
3. **Review templates** - Use the appropriate template for the issue type
4. **Add labels** - Apply relevant phase and priority labels
5. **Add to project board** - Use `gh project item-add` or GitHub MCP

### Example Workflow

```bash
# 1. Search existing issues
gh issue list --repo mikhashev/law7 --search "parser test"

# 2. If not found, create with template
gh issue create --repo mikhashev/law7 --template "feature_request.md" \
  --title "[FEAT] Add HTML parser tests" \
  --body "See template for structure"

# 3. Add labels
gh issue edit 13 --add-label "phase-1,tests,high-priority"

# 4. Add to project board
gh project item-add 2 --url "https://github.com/mikhashev/law7/issues/13"
```

## GitHub Project Management Tools

For GitHub project development workflow and management, two complementary tools are available:

### GitHub MCP Server (`github/github-mcp-server`)

The GitHub MCP server provides direct access to GitHub's API from within Claude Code sessions.

**Available tools include:**
- `issue_write` (create/update) - Create and update GitHub issues
- `add_issue_comment` - Add comments to issues and pull requests
- `list_issues` - List and filter issues
- `pull_request_read` - Get PR details, diffs, and status
- `create_pull_request` - Create pull requests
- `get_file_contents` - Read repository files
- `create_or_update_file` - Create or update files directly in the repo
- `push_files` - Push multiple files in a single commit
- `search_repositories` - Search across GitHub
- And more...

**When to use GitHub MCP:**
- Within Claude Code sessions (no CLI access needed)
- Creating and closing issues during development
- Managing pull requests and reviews
- Reading file contents from the repository

**Setup:**
The GitHub MCP server is configured in `.claude/settings.local.json` with:
- Token: Set via environment variable or directly in config
- Repository: Automatically detected from git remote (`mikhashev/law7`)

### GitHub CLI (`gh`)

The GitHub CLI is a command-line tool for GitHub operations, ideal for terminal workflows.

**Key commands for project management:**
```bash
# Project board operations
gh project list --owner mikhashev              # List all projects
gh project view <number>                       # View project details
gh project item-list <number>                  # List items in a project
gh project field-list <number>                 # View columns/fields
gh project item-add <number> --issue <id>      # Add issue to project

# Label management
gh label list --repo mikhashev/law7            # List all labels
gh label create <name> --color <hex>           # Create new label
gh label edit <name> --color <hex>             # Update label color

# Issue management
gh issue list --repo mikhashev/law7            # List issues
gh issue view <number>                         # View issue details
gh issue close <number>                        # Close an issue

# Authentication (when needed)
gh auth refresh -s read:project -h github.com  # Add project scopes
gh auth status                                  # Check auth status
```

**When to use GitHub CLI:**
- Project board setup and management (columns, fields)
- Bulk operations on labels and issues
- Direct terminal access outside Claude Code
- Project visualization and reporting

**Authentication:**
```bash
# Initial setup
gh auth login

# Add required scopes for project management
gh auth refresh -s read:project -h github.com

# Check current status
gh auth status
```

### Tool Selection Guide

| Task | Best Tool | Example |
|------|-----------|---------|
| Create/close issues during development | GitHub MCP | `issue_write` from Claude Code |
| Manage project board columns | GitHub CLI | `gh project field-list` |
| Add issues to project board | GitHub CLI | `gh project item-add` |
| Create/update labels | GitHub CLI | `gh label create/edit` |
| Bulk label operations | GitHub CLI | `gh label list --json` |
| Pull request management | GitHub MCP | `create_pull_request`, `pull_request_read` |
| File operations in repo | GitHub MCP | `create_or_update_file`, `push_files` |

## Recommended MCP Servers

| MCP Server | Purpose |
|------------|---------|
| **GitHub** (`github/github-mcp-server`) | Repository management: create issues, manage pull requests, push files, search code |
| **Context7** | Library documentation lookup |
| **Filesystem** | File operations |
| **Postgres** | Direct database queries during development |
| **Brave Search** | Research legal APIs and data sources |

## AI Task Management Workflow

For efficient Human+AI collaborative development, AI assistants should follow this structured workflow when working on tasks.

### Task Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│  Backlog    │────▶│  In Progress │────▶│  Review  │────▶│   Done    │────▶│ Archived │
│  (Planned)  │     │  (Working)   │     │(Check)   │     │(Closed)   │     │          │
└─────────────┘     └──────────────┘     └──────────┘     └───────────┘     └──────────┘
```

### 1. Task Discovery (Before Starting)

**When user requests work on a task:**
```bash
# Step 1: Check for existing issues
gh issue list --repo mikhashev/law7 --search "relevant keywords"

# Step 2: Check project board for in-progress items
gh project item-list 2 --owner mikhashev

# Step 3: Check git status for uncommitted changes
git status
```

**AI Decision Tree:**
- Is there an existing issue for this task?
  - **Yes** → Comment on issue, ask to assign it
  - **No** → Create new issue using appropriate template
- Is anyone working on related files?
  - **Yes** → Ask user if we should wait or coordinate
  - **No** → Proceed with task

### 2. Task Planning (Use TodoWrite)

**CRITICAL**: Always use TodoWrite tool to track task progress.

```python
# Create a todo list for multi-step tasks
TodoWrite([
    {"content": "Read relevant files", "status": "pending", "activeForm": "Reading relevant files"},
    {"content": "Implement feature", "status": "pending", "activeForm": "Implementing feature"},
    {"content": "Test changes", "status": "pending", "activeForm": "Testing changes"},
    {"content": "Commit and close issue", "status": "pending", "activeForm": "Committing and closing issue"}
])
```

**TodoWrite Best Practices:**
- Create todos for any task with 3+ steps
- Use descriptive `activeForm` (present continuous): "Reading files" not "Read files"
- Mark exactly ONE todo as `in_progress` at a time
- Mark todos as `completed` immediately after finishing
- Never batch-complete todos at the end

### 3. Task Execution

**While working on a task:**

1. **Update project board status** (when starting)
   ```bash
   # Move issue from Backlog to In Progress
   gh api graphql -f query='mutation { updateProjectV2ItemFieldValue(input: {projectId: "PVT_...", itemId: "PVTI_...", fieldId: "PVTSSF_...", value: {singleSelectOptionId: "47fc9ee4"}}) { item { id } } }'
   # "47fc9ee4" is the ID for "In Progress" status
   ```

2. **Update todos as you work**
   - Mark current step as `in_progress`
   - Complete steps immediately after finishing

3. **Comment on issue for progress updates**
   - Post updates for significant milestones
   - Note any blockers or discoveries

### 4. Completion Checklist

**Before marking a task as complete, verify:**

- [ ] All code follows project conventions (check existing patterns)
- [ ] Tests pass (run `npm test` or `poetry run pytest`)
- [ ] Build succeeds (run `npm run build` or equivalent)
- [ ] No new warnings introduced
- [ ] Documentation updated (if applicable)
- [ ] Commit message follows Conventional Commits format
- [ ] Issue referenced in commit message (`#issue_number`)
- [ ] Files committed and pushed (if working in branch)

### 5. Issue Status Transitions

**Move issues through the workflow:**

| Current State | Next State | When | How |
|---------------|------------|------|-----|
| Backlog | In Progress | Starting work | Update project board field |
| In Progress | Review | Ready for review | Comment "Ready for review" |
| Review | Done | After review/merge | Update project board, close issue |
| Any | Backlog | Blocked/cancelled | Comment with reason, move to backlog |

**Via GitHub CLI:**
```bash
# Move item to "Done"
gh api graphql -f query='mutation { updateProjectV2ItemFieldValue(input: {projectId: "PVT_...", itemId: "PVTI_...", fieldId: "PVTSSF_...", value: {singleSelectOptionId: "98236657"}}) { item { id } } }'
# "98236657" is the ID for "Done" status
```

### 6. Collaboration Patterns

**When AI should ask for human input:**

| Situation | Action | Example |
|-----------|--------|---------|
| Ambiguous requirements | Ask clarifying questions | "Should this handle edge case X?" |
| Multiple valid approaches | Present options, ask preference | "Option A: simpler, Option B: more flexible" |
| Breaking changes | Explicitly request approval | "This will change X, proceed?" |
| Missing context | Request additional information | "I need the database schema for X" |
| Task conflicts detected | Ask how to proceed | "Issue #7 also touches this file, coordinate?" |

**When AI should proceed autonomously:**

| Situation | Confidence Level | Example |
|-----------|------------------|---------|
| Following explicit patterns | High | Creating tests similar to existing ones |
| Refactoring within conventions | High | Extracting a function following existing style |
| Bug fixes with clear root cause | High | Fixing typo, adding missing import |
| Documentation updates | High | Adding docstrings to documented functions |
| Non-trivial implementation | Medium | Implementing feature from spec (verify after) |

### 7. Context Handoff Between Sessions

**When providing task summary:**

```markdown
## Task: [Brief description]

### Completed
- [x] Step 1 - Description
- [x] Step 2 - Description

### In Progress
- [ ] Step 3 - Current step (doing X, need to complete Y)

### Blocked/Next
- Next: Need to do Z
- Context: File A depends on change in file B
```

**Commit messages as handoff:**
```bash
# Use descriptive commit messages that provide context
git commit -m "feat(parser): add HTML table extraction for amendments

- Implemented table cell parsing for amendment documents
- Added support for nested tables
- Handles edge case of merged cells

Related: #6"
```

### 8. Example: Complete Task Workflow

```bash
# === STEP 1: Discovery ===
$ gh issue list --search "parser test"
# No existing issue found

# === STEP 2: Create Issue ===
$ gh issue create --template "feature_request.md" \
  --title "[FEAT] Add HTML parser tests" \
  --body "See template"

# === STEP 3: Add Labels ===
$ gh issue edit 13 --add-label "phase-1,tests,high-priority"

# === STEP 4: Add to Project Board ===
$ gh project item-add 2 --url "https://github.com/mikhashev/law7/issues/13"

# === STEP 5: Create Todo List ===
TodoWrite([
    {"content": "Read html_parser.py to understand structure", "status": "in_progress", "activeForm": "Reading html_parser.py"},
    {"content": "Create test_html_parser.py", "status": "pending", "activeForm": "Creating test file"},
    {"content": "Write tests for parse_html() function", "status": "pending", "activeForm": "Writing parse_html tests"},
    {"content": "Write tests for extract_amendments() function", "status": "pending", "activeForm": "Writing amendment extraction tests"},
    {"content": "Run tests and verify they pass", "status": "pending", "activeForm": "Running tests"},
    {"content": "Commit changes", "status": "pending", "activeForm": "Committing changes"}
])

# === STEP 6: Execute (with status updates) ===
# Move issue to In Progress
# Update todos as work progresses
# Comment milestones on issue

# === STEP 7: Complete ===
# Run tests
# Commit with conventional commit message
# Move issue to Done
# Close issue
```

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
