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
    STANDARD_NAMES,
    STANDARD_URL_HOSTS,
    check_glossary,
    find_number_violations,
    find_standard_host_violations,
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


def test_small_count_number_in_meaning_is_flagged():
    # "22 codes" is well under the old >= 1000 threshold; it must still be
    # caught because it names OUR coverage (a count noun), not because of
    # its magnitude.
    path = FIXTURES_DIR / "bad_small_count_number" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("'22'" in m and "count noun 'codes'" in m for m in messages), messages


def test_act_citation_missing_title_is_flagged():
    path = FIXTURES_DIR / "bad_missing_act_title" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any("No. 5-FZ" in m and "missing its quoted title" in m for m in messages), messages


def test_second_citation_segment_invalid_is_flagged():
    # A cell may hold several ';'-separated citations; the first segment
    # here is a well-formed act citation, but the second is not (no
    # number) -- it must be caught on its own, not waved through because
    # the first segment already carries the row.
    path = FIXTURES_DIR / "bad_segment_second_invalid" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any(
        "no recognized citation form" in m and "Presidential Decree 23.05.1996" in m
        for m in messages
    ), messages


def test_decree_of_the_president_written_out_is_accepted():
    # "Decree of the President of the Russian Federation" (and the shorter
    # "Decree of the President") is the actual written-out wording the
    # glossary uses for a presidential decree citation and must be
    # accepted like "Presidential Decree".
    path = FIXTURES_DIR / "good_decree_of_president" / "GLOSSARY.md"
    violations, _ = check_glossary(path, path.parent)
    assert violations == [], "\n".join(f"{v.line}: {v.message}" for v in violations)


def test_abbreviated_act_type_fz_of_is_rejected():
    # "FZ of ..." is an abbreviated act type, not the written-out "Federal
    # Law of ..." -- it must be rejected explicitly, not silently accepted
    # via the Code + art. path.
    path = FIXTURES_DIR / "bad_abbreviated_act_type" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any(
        "abbreviated act type" in m and "'FZ of'" in m and "write it out" in m for m in messages
    ), messages


def test_standard_cited_with_foreign_host_is_flagged():
    path = FIXTURES_DIR / "bad_standard_foreign_host" / "GLOSSARY.md"
    messages = _violation_messages(path)
    assert any(
        "URL host example.org is not a known home of standard ELI" in m for m in messages
    ), messages


@pytest.mark.parametrize(
    "fixture_name",
    [
        "bad_dangling_link",
        "bad_anchor",
        "bad_section1_repo_only",
        "bad_number_meaning",
        "bad_missing_number",
        "bad_small_count_number",
        "bad_missing_act_title",
        "bad_standard_foreign_host",
        "bad_segment_second_invalid",
        "bad_abbreviated_act_type",
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
# 3b. Numbers rule: frame of reference, not magnitude
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "meaning",
    [
        "The pipeline currently imports 22 codes.",
        "There are 19 codes today, down from 16 codes last year.",
        "We ship 13 tools and run 7 tests, 104 tests in the full suite.",
        "The corpus holds 6,232 articles as of today.",
        "Coverage stands at 22 of 23 codes so far.",
    ],
)
def test_our_coverage_numbers_are_flagged_regardless_of_size(meaning):
    problems = find_number_violations(meaning)
    assert problems, meaning


@pytest.mark.parametrize(
    "meaning",
    [
        "Published on 14.06.1994 under Federal Law No. 5-FZ.",
        "Measured on 2026-09-14, see the reconnaissance note.",
        "See Constitution of the Russian Federation, art. 54(1) and 54(2).",
        "OASIS LegalDocML, Akoma Ntoso v1.0, Part 2: Specifications.",
        "Superseded as a model by IFLA LRM (2017).",
        "See arXiv 2605.23497 (2026) for the measurement.",
    ],
)
def test_citation_numbers_are_not_flagged(meaning):
    assert find_number_violations(meaning) == [], meaning


def test_percentage_is_flagged():
    problems = find_number_violations("Roughly 42% of the corpus is covered.")
    assert any("42%" in p for p in problems), problems


def test_n_of_m_pattern_is_flagged_even_with_no_noun():
    problems = find_number_violations("It passes 22 of the 23 checks we run.")
    assert any("N of M" in p for p in problems), problems


def test_bare_large_number_without_noun_is_still_flagged():
    # No count noun anywhere nearby, but still >= 1000 -- the fallback rule.
    problems = find_number_violations("The figure quoted internally is 15000.")
    assert any("15000" in p and ">= 1000" in p for p in problems), problems


# ---------------------------------------------------------------------------
# 3c. Standard URL host allowlist
# ---------------------------------------------------------------------------


def test_standard_url_hosts_covers_every_standard_name():
    # Data-integrity check for the allowlist itself: every name the checker
    # recognizes as a standard must have a host list, or the "unknown
    # standard" fallback message would fire on every real citation of it.
    assert set(STANDARD_NAMES) == set(STANDARD_URL_HOSTS)


def test_matching_standard_host_has_no_violation():
    cell = "ELI ontology — https://data.europa.eu/eli/ontology"
    assert find_standard_host_violations(cell) == []


def test_foreign_standard_host_is_flagged():
    cell = "ELI ontology — https://example.org/eli-spec"
    problems = find_standard_host_violations(cell)
    assert any("example.org" in p and "ELI" in p for p in problems), problems


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
