# Phase 1: Foundation & Operational Excellence

**Duration:** Weeks 1-4
**Priority:** HIGH
**Status:** Not Started

---

## Overview

Build the operational foundation for all subsequent phases: GitHub project management, comprehensive test coverage, and code quality improvements.

---

## 1.1 GitHub Project Management Infrastructure

**Priority:** HIGH - Enables better tracking of all subsequent work

### Current State

Issue templates already exist (`.github/ISSUE_TEMPLATE/`):
- ✅ `bug_report.md`
- ✅ `feature_request.md`
- ✅ `documentation.md`
- ✅ `question.md`
- ✅ `PULL_REQUEST_TEMPLATE.md`

### Tasks

- [ ] Test GitHub plugin for project board management
- [ ] Create GitHub Project Board with columns: Backlog → In Progress → Review → Done
- [ ] Import ROADMAP items as issues
- [ ] Set up label system: `bug`, `enhancement`, `documentation`, `good first issue`, `Phase1-6`, `P0-P3`

### Label System

- `P0` - Critical (blocks release)
- `P1` - High priority (next release)
- `P2` - Medium priority (backlog)
- `P3` - Low priority (nice to have)

---

## 1.2 Test Coverage Expansion

**Priority:** HIGH - Critical for refactoring confidence

### Current State

Only encoding/parsing tests exist

### Target

70%+ coverage for critical paths

### Test Implementation Plan

#### MCP Tools Tests (`src/tools/*.test.ts`)

- [ ] `query-laws.test.ts` - Test semantic/keyword search with mocked DB
- [ ] `get-law.test.ts` - Test document retrieval
- [ ] `get-code-structure.test.ts` - Test consolidation queries
- [ ] `get-article-version.test.ts` - Test version history queries
- [ ] `trace-amendment-history.test.ts` - Test amendment tracking

#### Database Tests (`scripts/core/test_db.py`)

- [ ] Test PostgreSQL connection handling
- [ ] Test Qdrant vector operations
- [ ] Test Redis caching behavior
- [ ] Test batch saver operations

#### Parser Tests (`scripts/parser/test_*.py`)

- [ ] `test_html_parser.py` - Comprehensive parser testing
- [ ] `test_amendment_parser.py` - Amendment text parsing
- [ ] `test_ocr_fallback.py` - OCR fallback behavior

#### Consolidation Tests (`scripts/consolidation/test_*.py`)

- [ ] `test_amendment_parser.py` - Amendment extraction
- [ ] `test_diff_engine.py` - Article modification application
- [ ] `test_version_manager.py` - Version history tracking
- [ ] `test_consolidate.py` - End-to-end consolidation

### Files to Create/Modify

- `src/tools/*.test.ts` (7 test files)
- `scripts/core/test_db.py`
- `scripts/parser/test_html_parser.py`
- `scripts/consolidation/test_*.py` (4 test files)

---

## 1.3 Code Quality Improvements

**Priority:** MEDIUM - Improves maintainability

### Consolidate Duplicate Code Patterns

- [ ] Extract common retry logic into `scripts/utils/retry.py`
- [ ] Standardize error handling patterns across modules
- [ ] Create unified logging configuration (`scripts/core/logging.py`)
- [ ] Remove unused imports and dead code

### Standardize Error Handling

```python
# scripts/core/exceptions.py
class Law7Error(Exception):
    """Base exception for Law7"""

class Law7APIError(Law7Error):
    """API-related errors"""

class Law7ParserError(Law7Error):
    """Parser-related errors"""

class Law7DatabaseError(Law7Error):
    """Database-related errors"""
```

### Files to Create/Modify

- `scripts/utils/retry.py` (extract from existing code)
- `scripts/core/exceptions.py` (new)
- `scripts/core/logging.py` (new)
- Refactor existing modules to use new utilities

---

## Deliverables

- GitHub Project Board with all phases tracked
- Test suite with 70%+ coverage
- Refactored utilities (retry, exceptions, logging)
- Clean codebase with no unused imports

---

## Related Phases

- **Parallel with:** [Phase 0: P2P Research](./PHASE0_P2P_RESEARCH.md)
- **Enables:** All subsequent phases with testing and project tracking

---

## Timeline

**Week 1-2:** GitHub project setup, initial tests
**Week 3-4:** Code quality refactoring, remaining tests

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** None
**Blocking:** All subsequent phases (for tracking and testing confidence)
