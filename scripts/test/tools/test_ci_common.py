"""
Tests for the shared CI gate helpers (scripts/tools/ci/_common.py), in
particular the tool-version parsing and comparison that backs the
versioned-baseline scheme: a baseline count or known-failure id list is
only meaningful for the tool version it was measured with, so every
known_failures.txt section records a `version=` and the gate scripts
refuse to trust the recorded baseline when the running tool doesn't match.

Covers:
- `_extract_version` against real `--version` output shapes from ruff,
  tsc, vitest, pytest and python, and its failure mode on unparseable text
- `check_tool_version`: match, mismatch, and the "old-format allowlist
  with no version=" case, which must fail rather than silently pass
- `render_other_sections`: regenerating one tool's section must not drop
  another tool's section (or its own `version=`) from the same file
- `parse_allowlist` round-tripping a `version=` key inside a section
  without disturbing the plain-entry allowlist matching used by
  check_pytest.py / check_vitest.py
"""

from pathlib import Path

import pytest

from scripts.tools.ci._common import (
    Allowlist,
    Section,
    _extract_version,
    check_tool_version,
    parse_allowlist,
    render_other_sections,
)


# ---------------------------------------------------------------------------
# _extract_version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_output,expected",
    [
        ("ruff 0.8.6\n", "0.8.6"),
        ("ruff 0.16.7\n", "0.16.7"),
        ("Version 5.9.3\n", "5.9.3"),
        ("vitest/2.1.9 win32-x64 node-v24.18.0\n", "2.1.9"),
        ("pytest 8.4.2\n", "8.4.2"),
        ("Python 3.12.10\n", "3.12.10"),
    ],
)
def test_extract_version_parses_real_tool_output(raw_output, expected):
    assert _extract_version(raw_output, "tool") == expected


def test_extract_version_raises_on_unparseable_text():
    with pytest.raises(RuntimeError, match="could not parse a ruff version"):
        _extract_version("command not found", "ruff")


# ---------------------------------------------------------------------------
# check_tool_version
# ---------------------------------------------------------------------------


def _section(**kv) -> Section:
    return Section(name="ruff", kv=dict(kv))


def test_check_tool_version_matches_returns_none():
    section = _section(version="0.8.6", baseline="200")
    assert check_tool_version(section, "0.8.6", "ruff", "known_failures.txt") is None


def test_check_tool_version_mismatch_fails_with_both_versions_named():
    section = _section(version="0.8.6", baseline="200")
    message = check_tool_version(section, "0.16.7", "ruff", "scripts/test/known_failures.txt")
    assert message is not None
    assert "ruff 0.16.7" in message
    assert "0.8.6" in message
    assert "re-measure" in message
    assert "scripts/test/known_failures.txt" in message


def test_check_tool_version_no_section_fails_as_unknown():
    message = check_tool_version(None, "0.8.6", "ruff", "scripts/test/known_failures.txt")
    assert message is not None
    assert "no recorded baseline tool version" in message


def test_check_tool_version_old_format_section_without_version_fails():
    # Simulates a known_failures.txt written before this check existed:
    # the section exists (e.g. has a baseline) but has no version= key.
    section = _section(baseline="200")
    message = check_tool_version(section, "0.8.6", "ruff", "scripts/test/known_failures.txt")
    assert message is not None
    assert "no recorded baseline tool version" in message


# ---------------------------------------------------------------------------
# render_other_sections
# ---------------------------------------------------------------------------


def test_render_other_sections_preserves_unskipped_sections_in_order():
    sections = {
        "pytest": Section(name="pytest", kv={"version": "8.4.2"}),
        "ruff": Section(name="ruff", kv={"version": "0.8.6", "baseline": "200"}),
    }
    rendered = render_other_sections(sections, skip={"ruff"})
    text = "\n".join(rendered)
    assert "[pytest]" in text
    assert "version=8.4.2" in text
    # The skipped section's own content must not appear -- the caller is
    # responsible for writing its own fresh [ruff] block elsewhere.
    assert "[ruff]" not in text
    assert "baseline=200" not in text


def test_render_other_sections_preserves_plain_lines_and_kv_together():
    # Mirrors [tsc-files]: a version=/baseline= kv pair plus a list of
    # allowlisted file paths as plain lines.
    sections = {
        "tsc-files": Section(
            name="tsc-files",
            kv={"version": "5.9.3", "baseline": "1"},
            lines=["src/some/file.ts"],
        ),
    }
    rendered = render_other_sections(sections, skip={"vitest"})
    assert rendered == [
        "",
        "[tsc-files]",
        "version=5.9.3",
        "baseline=1",
        "src/some/file.ts",
    ]


def test_render_other_sections_empty_when_only_section_is_skipped():
    sections = {"ruff": Section(name="ruff", kv={"version": "0.8.6"})}
    assert render_other_sections(sections, skip={"ruff"}) == []


# ---------------------------------------------------------------------------
# parse_allowlist round-trip with a version= section
# ---------------------------------------------------------------------------


def test_parse_allowlist_reads_version_without_disturbing_entries(tmp_path: Path):
    path = tmp_path / "known_failures.txt"
    path.write_text(
        "\n".join(
            [
                "# header comment, ignored",
                "",
                "scripts/test/some_test.py::test_still_broken",
                "",
                "[pytest]",
                "version=8.4.2",
                "",
                "[ruff]",
                "version=0.8.6",
                "baseline=200",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    allow = parse_allowlist(path)

    # The plain pytest node id stays a top-level "entry" (what
    # check_pytest.py diffs known failures against) -- it must not be
    # swallowed by the section parsing that follows it in the file.
    assert allow.entries == ["scripts/test/some_test.py::test_still_broken"]

    assert allow.sections["pytest"].kv == {"version": "8.4.2"}
    assert allow.sections["ruff"].kv == {"version": "0.8.6", "baseline": "200"}


def test_parse_allowlist_missing_file_returns_empty_allowlist(tmp_path: Path):
    allow = parse_allowlist(tmp_path / "does-not-exist.txt")
    assert allow == Allowlist(entries=[], sections={})
