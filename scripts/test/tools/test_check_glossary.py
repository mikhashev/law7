"""
Tests for the glossary checker (scripts/tools/check_glossary.py).

Covers:
- the checker passing on a small well-formed fixture
- the checker failing on fixtures that exercise each violation kind
  (dangling link, bad anchor, section-1-cites-repo, number in Meaning,
  act citation missing its number)
- the GitHub heading-slug helper
- running the checker against the scratchpad copy of the real glossary
  draft, purely to report what it currently flags (not asserted, since
  the draft is expected to be revised)
"""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.tools.check_glossary import (
    check_glossary,
    github_slug,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER_SCRIPT = REPO_ROOT / "scripts" / "tools" / "check_glossary.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# The real glossary lives in docs/GLOSSARY.md. Until it is committed the
# smoke test below skips instead of failing.
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRATCHPAD_GLOSSARY = REPO_ROOT / "docs" / "GLOSSARY.md"


def _violation_messages(path: Path, base_dir: Path | None = None) -> list[str]:
    violations, _verbose_rows = check_glossary(path, base_dir or path.parent)
    return [f"{path}:{v.line}: {v.message}" for v in violations]


# ---------------------------------------------------------------------------
# 1. Passes on a small good fixture
# ---------------------------------------------------------------------------


def test_good_fixture_has_no_violations():
    path = FIXTURES_DIR / "good" / "GLOSSARY.md"
    violations, _ = check_glossary(path, path.parent)
    assert violations == [], "\n".join(f"{v.line}: {v.message}" for v in violations)


def test_good_fixture_cli_exits_zero():
    path = FIXTURES_DIR / "good" / "GLOSSARY.md"
    result = subprocess.run(
        [sys.executable, str(CHECKER_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# 2. Fails on each violation kind
# ---------------------------------------------------------------------------


def test_dangling_link_is_flagged():
    path = FIXTURES_DIR / "bad_dangling_link" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("Nowhere.md" in m and "not found" in m for m in messages), messages


def test_bad_anchor_is_flagged():
    path = FIXTURES_DIR / "bad_anchor" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("no-such-anchor" in m and "anchor" in m for m in messages), messages


def test_section1_repo_only_is_flagged():
    path = FIXTURES_DIR / "bad_section1_repo_only" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("cites the repo instead of an act" in m for m in messages), messages


def test_number_in_meaning_is_flagged():
    path = FIXTURES_DIR / "bad_number_meaning" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("157,730" in m for m in messages), messages


def test_act_citation_missing_number_is_flagged():
    path = FIXTURES_DIR / "bad_missing_number" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("no recognized citation" in m for m in messages), messages


@pytest.mark.parametrize(
    "fixture_name",
    [
        "bad_dangling_link",
        "bad_anchor",
        "bad_section1_repo_only",
        "bad_number_meaning",
        "bad_missing_number",
    ],
)
def test_bad_fixtures_cli_exits_one(fixture_name):
    path = FIXTURES_DIR / fixture_name / "GLOSSARY.md"
    result = subprocess.run(
        [sys.executable, str(CHECKER_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.strip() != ""


# ---------------------------------------------------------------------------
# 3. Slug function unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "heading,expected",
    [
        ("## 1. Two columns", "1-two-columns"),
        ("1. Two columns", "1-two-columns"),
        ("Database Schema", "database-schema"),
        ("### 4. Verification", "4-verification"),
        ("Country Adapter Pattern", "country-adapter-pattern"),
        ("What's left?", "whats-left"),
        ("Two   columns", "two-columns"),
        (
            "`textualMod` / active and passive modifications",
            "textualmod-active-and-passive-modifications",
        ),
    ],
)
def test_github_slug(heading, expected):
    assert github_slug(heading) == expected


def test_github_slug_is_idempotent_on_bare_text():
    # Passing the already-slugified text back in should be a no-op.
    slug = github_slug("## 1. Two columns")
    assert github_slug(slug) == slug


# ---------------------------------------------------------------------------
# 4. Report (do not assert) what the checker flags on the real draft
# ---------------------------------------------------------------------------


def test_report_violations_on_scratchpad_draft():
    if not SCRATCHPAD_GLOSSARY.exists():
        pytest.skip(f"docs/GLOSSARY.md not present yet: {SCRATCHPAD_GLOSSARY}")

    base_dir = REPO_ROOT / "docs"
    violations, verbose_rows = check_glossary(SCRATCHPAD_GLOSSARY, base_dir)

    lines = [
        f"\n--- check_glossary report for {SCRATCHPAD_GLOSSARY} ---",
        f"base-dir: {base_dir}",
        f"{len(verbose_rows)} rows checked in sections 1-3",
    ]
    if violations:
        lines.append(f"{len(violations)} violation(s) found:")
        lines.extend(f"  {SCRATCHPAD_GLOSSARY}:{v.line}: {v.message}" for v in violations)
    else:
        lines.append("no violations found")
    lines.append("--- end report ---\n")

    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        # Some Windows consoles use a legacy codepage that cannot render the
        # Cyrillic glosses in the draft's Term cells (this only bites when
        # output isn't captured, e.g. `pytest -s`). Fall back to an
        # ASCII-safe rendering so the report is still visible.
        for line in lines:
            print(line.encode("ascii", errors="backslashreplace").decode("ascii"))

    # Intentionally not asserted: the draft is expected to be revised, and
    # this test exists to surface what the checker currently flags, not to
    # gate on it.
    assert isinstance(violations, list)
