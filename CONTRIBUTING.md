# Contributing to Law7

Thanks for your interest in contributing! This guide explains how to get involved.

## Getting Started

1. Fork the repository and clone it locally
2. Install dependencies:

**TypeScript (MCP Server):**
```bash
npm install
npm run build
```

**Python (Data Pipeline):**
```bash
poetry install
```

3. Start Docker services:
```bash
cd docker
docker-compose up -d
```

4. Run dev server:
```bash
npm run dev
```

## Development Process

1. Create a new branch for your changes from `main`
2. Make changes following existing code style and conventions
3. Test changes locally
4. Update documentation as needed
5. Use clear commit messages (see [Conventional Commits](#commit-conventions))
6. Submit a pull request
7. PRs will be reviewed by maintainers

## Commit Conventions

This project uses **Conventional Commits** format:

```
<type>(<scope>): <description>
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `refactor` - Code refactoring
- `test` - Test additions or changes
- `chore` - Build, tooling, dependency updates

**Examples:**
```
feat(db): add connection pooling for PostgreSQL
fix(crawler): handle rate limiting errors from pravo.gov.ru
docs(readme): update installation instructions
```

## Code Style

### TypeScript
- Strict mode enabled
- Use `prettier` for formatting
- Run `npm run build` before committing

### Python
- Use `black` formatter (line-length: 100)
- Use `ruff` for linting
- Run tests: `poetry run pytest`

## Testing

- **MCP Server:** Test with `npx @modelcontextprotocol/inspector node dist/index.js`
- **Python:** Run `poetry run pytest`
- **Database:** Ensure PostgreSQL, Qdrant, and Redis are running

## AI-Assisted Development

If you're using AI assistants (Claude Code, Cursor) for development, see [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md) for AI-specific guidelines and workflows.

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## Security

If you find a security vulnerability, please refer to our [Security Policy](SECURITY.md) for reporting instructions.

## Questions?

- Feel free to [open an issue](https://github.com/mikhashev/law7/issues) for questions
- Check existing issues for similar discussions
- Review [docs/](docs/) for additional documentation

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0 license](LICENSE).
