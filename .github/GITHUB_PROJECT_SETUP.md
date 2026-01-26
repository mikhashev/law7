# GitHub Project Board Setup Guide

This document describes how to set up and configure a GitHub Project Board for Law7 development tracking.

## Overview

The GitHub Project Board will track all tasks from the refactoring plan (see [Enhancement Roadmap v2](../law7_enhancement_roadmap_v2.md) and [Phase Plans](../docs/)).

## Project Board Structure

### Columns (Statuses)

| Column | Description |
|--------|-------------|
| **Backlog** | Tasks not yet started, ready to be prioritized |
| **In Progress** | Tasks currently being worked on |
| **Review** | Tasks completed, pending code review |
| **Done** | Tasks completed and merged |

### Labels

| Label | Color | Purpose |
|-------|-------|---------|
| `phase-0` | purple | P2P Architecture Research |
| `phase-1` | blue | Foundation & Operational Excellence |
| `phase-2` | green | Performance Fixes |
| `phase-3` | yellow | OCR Enhancement |
| `phase-4` | orange | Regional Legislation |
| `phase-5` | red | Judicial Practice |
| `phase-6` | gray | Official Interpretations |
| `phase-7` | pink | Structure Refactoring |
| `bug` | red | Bug fixes |
| `enhancement` | blue | Feature enhancements |
| `documentation` | green | Documentation updates |
| `tests` | yellow | Test coverage |
| `critical` | red | Critical path items |
| `high-priority` | orange | High priority |
| `medium-priority` | yellow | Medium priority |
| `low-priority` | gray | Low priority |

## Using GitHub MCP Server (Claude Code)

The GitHub MCP server is already installed and configured at:
https://github.com/github/github-mcp-server

Available tools include:
- `create_issue` - Create GitHub issues
- `create_pull_request` - Create pull requests
- `fork_repository` - Fork repositories
- `push_files` - Push files to branches

### Creating Issues from ROADMAP

Use the GitHub MCP server tools to create issues programmatically from the ROADMAP.md items.

## Issue Templates

The following issue templates are available in `.github/ISSUE_TEMPLATE/`:

- `bug_report.md` - For reporting bugs
- `feature_request.md` - For suggesting new features
- `documentation.md` - For documentation improvements
- `question.md` - For asking questions

## Reference Links

- **Main Refactoring Plan**: [law7_enhancement_roadmap_v2.md](../law7_enhancement_roadmap_v2.md)
- **Phase Plans**: [docs/](../docs/)
- **Project ROADMAP**: [docs/ROADMAP.md](../docs/ROADMAP.md)
- **AI Workflow**: [docs/AI_WORKFLOW.md](../docs/AI_WORKFLOW.md)

---

**Created**: January 2026
**Status**: Ready for implementation
