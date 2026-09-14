"""
Tests for the shared CI gate helpers (scripts/tools/ci/_common.py) and for
the two-sided behaviour of the gate scripts themselves, in particular the
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
- the `# ^` note form: kept out of `entries`, carried through `--generate`,
  dropped with its id, and the three malformed-file cases that must exit 1
  rather than be silently tolerated (orphan note, inline `#`, bare line
  under a key=value-only section)
- the two-sided gates: a stale allowlist entry (pytest/vitest) and a ruff
  count below the baseline each exit 1, because an unused allowance is a
  pre-issued permission for the next failure
"""

import json
import sys
from pathlib import Path

import pytest

from scripts.tools.ci import check_pytest, check_ruff, check_vitest
from scripts.tools.ci._common import (
    Allowlist,
    AllowlistError,
    Section,
    _extract_version,
    check_tool_version,
    parse_allowlist,
    render_entries,
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


# ---------------------------------------------------------------------------
# helpers for the allowlist-file and gate-script tests below
# ---------------------------------------------------------------------------


def _write(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run(module, *argv) -> int:
    """Call a gate script's main() with the given command line."""
    old_argv = sys.argv
    sys.argv = [module.__name__, *argv]
    try:
        return module.main()
    finally:
        sys.argv = old_argv


def _junit_xml(tmp_path: Path, failing_ids) -> Path:
    """Write a minimal pytest JUnit XML report.

    The ids use a dotted classname that does not resolve to a real file on
    disk, so testcase_id falls back to "classname::name" and the expected
    node ids stay stable regardless of the repo layout.
    """
    cases = []
    for node_id in failing_ids:
        classname, _, name = node_id.rpartition("::")
        cases.append(
            '<testcase classname="' + classname + '" name="' + name + '">'
            '<failure message="x"/></testcase>'
        )
    xml = '<testsuites><testsuite name="pytest">' + "".join(cases) + "</testsuite></testsuites>"
    path = tmp_path / "report.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def _vitest_report(tmp_path: Path, failing) -> Path:
    results = [
        {
            "name": str(check_vitest.REPO_ROOT / "src" / "test" / "x.test.ts"),
            "assertionResults": [{"status": "failed", "fullName": name} for name in failing],
        }
    ]
    path = tmp_path / "vitest.json"
    path.write_text(json.dumps({"testResults": results}), encoding="utf-8")
    return path


def _ruff_report(tmp_path: Path, count: int) -> Path:
    path = tmp_path / "ruff.json"
    path.write_text(json.dumps([{"code": "E501"}] * count), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# "# ^" note lines
# ---------------------------------------------------------------------------


def test_note_line_attaches_to_the_entry_above_and_stays_out_of_entries(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "# plain header comment",
        "scripts/test/x.py::test_y",
        "# ^ broken since migration 003, see audit/PLAN stage 3",
        "scripts/test/z.py::test_w",
        "",
        "[pytest]",
        "version=8.4.2",
    )

    allow = parse_allowlist(path)

    # A note must never become an entry: an "entry" that matches no test id
    # would look like one more allowlisted failure, forever.
    assert allow.entries == ["scripts/test/x.py::test_y", "scripts/test/z.py::test_w"]
    assert allow.notes["scripts/test/x.py::test_y"] == [
        "# ^ broken since migration 003, see audit/PLAN stage 3"
    ]
    assert allow.notes["scripts/test/z.py::test_w"] == []


def test_plain_comment_after_an_entry_is_not_a_note(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "scripts/test/x.py::test_y",
        "# just a comment, attaches to nothing",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    allow = parse_allowlist(path)
    assert allow.notes["scripts/test/x.py::test_y"] == []


def test_render_entries_carries_notes_forward_and_drops_them_with_the_id():
    notes = {
        "a.py::test_kept": ["# ^ still broken, see stage 3"],
        "a.py::test_gone": ["# ^ note that must die with its id"],
    }
    rendered = render_entries(["a.py::test_kept"], notes)
    assert rendered == ["a.py::test_kept", "# ^ still broken, see stage 3"]
    assert "# ^ note that must die with its id" not in rendered


def test_generate_keeps_the_note_of_a_still_failing_id(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "fake.module::test_still_broken",
        "# ^ see audit/PLAN stage 3",
        "fake.module::test_fixed",
        "# ^ note that must disappear with its id",
        "",
        "[pytest]",
        "version=8.4.2",
        "",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_pytest, "ALLOWLIST_PATH", path)
    junit = _junit_xml(tmp_path, ["fake.module::test_still_broken"])

    code = _run(
        check_pytest, "--junit-xml", str(junit), "--override-version", "8.4.2", "--generate"
    )
    assert code == 0

    text = path.read_text(encoding="utf-8")
    assert "# ^ see audit/PLAN stage 3" in text
    # The fixed test and its note are both gone.
    assert "fake.module::test_fixed" not in text
    assert "note that must disappear" not in text
    # ... and the unrelated [ruff] section survived the rewrite.
    assert "baseline=200" in text

    reparsed = parse_allowlist(path)
    assert reparsed.entries == ["fake.module::test_still_broken"]
    assert reparsed.notes["fake.module::test_still_broken"] == ["# ^ see audit/PLAN stage 3"]


def test_render_other_sections_carries_notes_on_section_lines():
    sections = {
        "tsc-files": Section(
            name="tsc-files",
            kv={"version": "5.9.3", "baseline": "1"},
            lines=["src/some/file.ts"],
            notes={"src/some/file.ts": ["# ^ blocked on the Phase 7A shim"]},
        ),
    }
    assert render_other_sections(sections, skip=set()) == [
        "",
        "[tsc-files]",
        "version=5.9.3",
        "baseline=1",
        "src/some/file.ts",
        "# ^ blocked on the Phase 7A shim",
    ]


# ---------------------------------------------------------------------------
# malformed allowlists must exit 1, not be silently tolerated
# ---------------------------------------------------------------------------


def test_orphan_note_line_is_rejected(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "# ^ a note with nothing above it",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    with pytest.raises(AllowlistError, match="no entry to attach to"):
        parse_allowlist(path)


def test_note_separated_from_its_entry_by_a_blank_line_is_rejected(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "a.py::test_x",
        "",
        "# ^ detached note",
    )
    with pytest.raises(AllowlistError, match="directly below"):
        parse_allowlist(path)


def test_inline_hash_comment_on_an_entry_is_rejected(tmp_path: Path):
    path = _write(tmp_path / "known_failures.txt", "a.py::test  # note")
    with pytest.raises(AllowlistError) as excinfo:
        parse_allowlist(path)
    message = str(excinfo.value)
    assert "inline '#'" in message
    # The message has to say where the note actually goes.
    assert "# ^" in message


def test_bare_line_under_a_key_value_section_is_rejected(tmp_path: Path):
    # The dangerous typo: a node id written below the [pytest] header instead
    # of above it. It allowlists nothing, so the gate would pass for the
    # wrong reason -- silently, before this check.
    path = _write(
        tmp_path / "known_failures.txt",
        "[pytest]",
        "version=8.4.2",
        "scripts/test/x.py::test_y",
    )
    with pytest.raises(AllowlistError, match="key=value"):
        parse_allowlist(path)


def test_bare_lines_are_still_data_under_tsc_files(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "[tsc-files]",
        "version=5.9.3",
        "src/some/file.ts",
        "# ^ blocked on the Phase 7A shim",
        "baseline=1",
    )
    allow = parse_allowlist(path)
    section = allow.sections["tsc-files"]
    assert section.lines == ["src/some/file.ts"]
    assert section.notes["src/some/file.ts"] == ["# ^ blocked on the Phase 7A shim"]
    assert section.kv == {"version": "5.9.3", "baseline": "1"}


def test_malformed_allowlist_makes_the_gate_exit_1(tmp_path: Path, monkeypatch, capsys):
    path = _write(tmp_path / "known_failures.txt", "a.py::test  # note")
    monkeypatch.setattr(check_pytest, "ALLOWLIST_PATH", path)
    junit = _junit_xml(tmp_path, [])

    code = _run(check_pytest, "--junit-xml", str(junit), "--override-version", "8.4.2")

    assert code == 1
    assert "malformed allowlist" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# two-sided gates: stale entries and a fallen ruff count also fail
# ---------------------------------------------------------------------------


def test_pytest_gate_fails_on_a_stale_allowlist_entry(tmp_path: Path, monkeypatch, capsys):
    path = _write(
        tmp_path / "known_failures.txt",
        "fake.module::test_fixed_but_still_listed",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    monkeypatch.setattr(check_pytest, "ALLOWLIST_PATH", path)
    junit = _junit_xml(tmp_path, [])  # nothing fails any more

    code = _run(check_pytest, "--junit-xml", str(junit), "--override-version", "8.4.2")

    out = capsys.readouterr().out
    assert code == 1
    assert "fake.module::test_fixed_but_still_listed" in out
    assert "pre-issued permission" in out
    assert "--generate" in out


def test_pytest_gate_passes_when_every_entry_still_fails(tmp_path: Path, monkeypatch, capsys):
    path = _write(
        tmp_path / "known_failures.txt",
        "fake.module::test_broken",
        "# ^ see audit/PLAN stage 3",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    monkeypatch.setattr(check_pytest, "ALLOWLIST_PATH", path)
    junit = _junit_xml(tmp_path, ["fake.module::test_broken"])

    code = _run(check_pytest, "--junit-xml", str(junit), "--override-version", "8.4.2")

    assert code == 0
    assert "1 known failure(s)" in capsys.readouterr().out


def test_vitest_gate_fails_on_a_stale_allowlist_entry(tmp_path: Path, monkeypatch, capsys):
    path = _write(
        tmp_path / "known_failures.txt",
        "src/test/x.test.ts > suite > passes now",
        "",
        "[vitest]",
        "version=2.1.9",
    )
    monkeypatch.setattr(check_vitest, "ALLOWLIST_PATH", path)
    report = _vitest_report(tmp_path, [])

    code = _run(check_vitest, "--json-report", str(report), "--override-version", "2.1.9")

    out = capsys.readouterr().out
    assert code == 1
    assert "src/test/x.test.ts > suite > passes now" in out
    assert "pre-issued permission" in out
    assert "--generate" in out


def test_vitest_gate_passes_when_the_listed_test_still_fails(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "src/test/x.test.ts > suite > still broken",
        "",
        "[vitest]",
        "version=2.1.9",
    )
    monkeypatch.setattr(check_vitest, "ALLOWLIST_PATH", path)
    report = _vitest_report(tmp_path, ["suite > still broken"])

    code = _run(check_vitest, "--json-report", str(report), "--override-version", "2.1.9")
    assert code == 0


@pytest.mark.parametrize("count,expected", [(199, 1), (200, 0), (201, 1)])
def test_ruff_gate_is_two_sided(tmp_path: Path, monkeypatch, count, expected):
    path = _write(
        tmp_path / "known_failures.txt",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    report = _ruff_report(tmp_path, count)

    code = _run(check_ruff, "--json-report", str(report), "--override-version", "0.8.6")
    assert code == expected


def test_ruff_gate_names_the_new_count_and_how_to_lower_it(tmp_path: Path, monkeypatch, capsys):
    path = _write(
        tmp_path / "known_failures.txt",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    report = _ruff_report(tmp_path, 190)

    code = _run(check_ruff, "--json-report", str(report), "--override-version", "0.8.6")

    out = capsys.readouterr().out
    assert code == 1
    assert "fell to 190" in out
    assert "baseline is 200" in out
    assert "check_ruff.py --generate" in out


def test_ruff_generate_writes_the_new_count_and_version(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "fake.module::test_broken",
        "# ^ see audit/PLAN stage 3",
        "",
        "[pytest]",
        "version=8.4.2",
        "",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    report = _ruff_report(tmp_path, 190)

    code = _run(
        check_ruff, "--json-report", str(report), "--override-version", "0.16.7", "--generate"
    )
    assert code == 0

    allow = parse_allowlist(path)
    assert allow.sections["ruff"].kv == {"version": "0.16.7", "baseline": "190"}
    # The pytest half of the same file -- entry, note and version -- survives.
    assert allow.entries == ["fake.module::test_broken"]
    assert allow.notes["fake.module::test_broken"] == ["# ^ see audit/PLAN stage 3"]
    assert allow.sections["pytest"].kv == {"version": "8.4.2"}

    # ... and the gate it just rewrote now passes at the new count.
    assert _run(check_ruff, "--json-report", str(report), "--override-version", "0.16.7") == 0
