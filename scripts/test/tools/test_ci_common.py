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
  dropped with its id, and the malformed-file cases that must exit 1 rather
  than be silently tolerated (orphan note, inline `#`, bare line under a
  key=value-only section)
- the note requirement in both directions: an entry with no note below it is
  an error too, for pytest/vitest ids and `[tsc-files]` paths alike, so the
  headers' "never add an entry without a linked issue/stage note" is a rule
  the parser enforces rather than advice the reader may skip
- `--generate` leaving a trail: it refuses without `--reason`, prints the
  was -> now delta, records one `regenerated=<date> <reason>` line, writes a
  TODO note under ids it has just measured, and refuses an
  `--override-version` that differs from the installed tool (a baseline may
  only carry the version that measured it)
- the two-sided gates: a stale allowlist entry (pytest/vitest) and a ruff
  count below the baseline each exit 1, because an unused allowance is a
  pre-issued permission for the next failure
"""

import json
import sys
from pathlib import Path

import pytest

from scripts.tools.ci import check_pytest, check_ruff, check_tsc, check_vitest
from scripts.tools.ci._common import (
    Allowlist,
    AllowlistError,
    Section,
    _extract_version,
    check_tool_version,
    fill_missing_notes,
    parse_allowlist,
    render_entries,
    render_other_sections,
    utc_today,
    was_now_line,
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
                "# ^ see audit/PLAN stage 3",
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
        "# ^ also stage 3",
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
    assert allow.notes["scripts/test/z.py::test_w"] == ["# ^ also stage 3"]


def test_plain_comment_after_an_entry_does_not_count_as_the_note(tmp_path: Path):
    # A '# ...' comment attaches to nothing, so the entry above it is an
    # entry without a note -- which is now the error, not a tolerated shape.
    path = _write(
        tmp_path / "known_failures.txt",
        "scripts/test/x.py::test_y",
        "# just a comment, attaches to nothing",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    with pytest.raises(AllowlistError, match="has no note"):
        parse_allowlist(path)


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
    monkeypatch.setattr(check_pytest, "get_pytest_version", lambda: "8.4.2")
    junit = _junit_xml(tmp_path, ["fake.module::test_still_broken"])

    code = _run(
        check_pytest,
        "--junit-xml",
        str(junit),
        "--override-version",
        "8.4.2",
        "--generate",
        "--reason",
        "test fixture",
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
    # The blank line ends the entry, so two rules fire at once: the entry
    # never got its note, and the note has nothing above it. Either message
    # is fine; what matters is that the file does not parse, because the
    # note reads as attached to the naked eye and attaches to nothing.
    path = _write(
        tmp_path / "known_failures.txt",
        "a.py::test_x",
        "",
        "# ^ detached note",
    )
    with pytest.raises(AllowlistError, match="has no note|directly below"):
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
        "# ^ see audit/PLAN stage 3",
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
        "# ^ see audit/PLAN stage 3",
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
        "# ^ see audit/PLAN stage 3",
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
    # --generate may not assert a version nothing measured, so the override
    # has to agree with the installed tool: pretend ruff 0.16.7 is installed.
    monkeypatch.setattr(check_ruff, "get_ruff_version", lambda: "0.16.7")
    report = _ruff_report(tmp_path, 190)

    code = _run(
        check_ruff,
        "--json-report",
        str(report),
        "--override-version",
        "0.16.7",
        "--generate",
        "--reason",
        "ruff 0.16.7 bump",
    )
    assert code == 0

    allow = parse_allowlist(path)
    assert allow.sections["ruff"].kv["version"] == "0.16.7"
    assert allow.sections["ruff"].kv["baseline"] == "190"
    # The pytest half of the same file -- entry, note and version -- survives.
    assert allow.entries == ["fake.module::test_broken"]
    assert allow.notes["fake.module::test_broken"] == ["# ^ see audit/PLAN stage 3"]
    assert allow.sections["pytest"].kv == {"version": "8.4.2"}

    # ... and the gate it just rewrote now passes at the new count.
    assert _run(check_ruff, "--json-report", str(report), "--override-version", "0.16.7") == 0


def _tsc_log(tmp_path: Path, error_files) -> Path:
    path = tmp_path / "tsc.log"
    path.write_text(
        "\n".join(f"{f}(1,2): error TS2345: nope." for f in error_files) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# the note rule runs in both directions: an entry with no note fails too
# ---------------------------------------------------------------------------
#
# The headers have always said "never add an entry without a linked
# issue/stage note", but only the reverse (a note with no entry) was checked,
# so that sentence was advice. An allowance nobody can trace to an issue or a
# stage is an allowance nobody ever retires.


def test_entry_without_a_note_is_rejected_naming_path_and_line(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "a.py::test_documented",
        "# ^ see audit/PLAN stage 3",
        "a.py::test_undocumented",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    with pytest.raises(AllowlistError) as excinfo:
        parse_allowlist(path)
    message = str(excinfo.value)
    assert "has no note" in message
    assert "# ^" in message
    # path:line of the entry itself, not of the line that ended it.
    assert f"{path}:3" in message
    assert "a.py::test_undocumented" in message


def test_entry_without_a_note_at_end_of_file_is_rejected(tmp_path: Path):
    # Nothing follows the entry, so the check has to fire at EOF as well --
    # otherwise the last entry in every file would be exempt from the rule.
    path = _write(tmp_path / "known_failures.txt", "a.py::test_last_line")
    with pytest.raises(AllowlistError, match="has no note"):
        parse_allowlist(path)


def test_tsc_files_path_without_a_note_is_rejected(tmp_path: Path):
    # [tsc-files] is the one section whose bare lines are entries, so the
    # same rule applies to them.
    path = _write(
        tmp_path / "known_failures.txt",
        "[tsc-files]",
        "version=5.9.3",
        "src/some/file.ts",
        "baseline=1",
    )
    with pytest.raises(AllowlistError, match="has no note"):
        parse_allowlist(path)


def test_a_multi_line_note_satisfies_the_requirement(tmp_path: Path):
    path = _write(
        tmp_path / "known_failures.txt",
        "a.py::test_x",
        "# ^ blocked on the Phase 7A shim,",
        "# ^ see audit/PLAN stage 3",
    )
    allow = parse_allowlist(path)
    assert allow.notes["a.py::test_x"] == [
        "# ^ blocked on the Phase 7A shim,",
        "# ^ see audit/PLAN stage 3",
    ]


def test_an_entry_without_a_note_makes_the_gate_exit_1(tmp_path: Path, monkeypatch, capsys):
    path = _write(
        tmp_path / "known_failures.txt",
        "fake.module::test_broken",
        "",
        "[pytest]",
        "version=8.4.2",
    )
    monkeypatch.setattr(check_pytest, "ALLOWLIST_PATH", path)
    junit = _junit_xml(tmp_path, ["fake.module::test_broken"])

    code = _run(check_pytest, "--junit-xml", str(junit), "--override-version", "8.4.2")

    out = capsys.readouterr().out
    assert code == 1
    assert "malformed allowlist" in out
    assert "has no note" in out


def test_fill_missing_notes_only_fills_the_gaps():
    notes = {"a.py::test_known": ["# ^ see audit/PLAN stage 3"]}
    filled = fill_missing_notes(["a.py::test_known", "a.py::test_new"], notes)
    assert filled["a.py::test_known"] == ["# ^ see audit/PLAN stage 3"]
    assert filled["a.py::test_new"] == [f"# ^ TODO: reason (added by --generate {utc_today()})"]
    # The caller's dict is not mutated: --generate reuses the parsed notes.
    assert "a.py::test_new" not in notes


def test_pytest_generate_writes_a_todo_note_under_a_newly_measured_id(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "[pytest]",
        "version=8.4.2",
    )
    monkeypatch.setattr(check_pytest, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_pytest, "get_pytest_version", lambda: "8.4.2")
    junit = _junit_xml(tmp_path, ["fake.module::test_newly_broken"])

    code = _run(
        check_pytest, "--junit-xml", str(junit), "--generate", "--reason", "stage 3 fallout"
    )
    assert code == 0

    text = path.read_text(encoding="utf-8")
    assert "# ^ TODO: reason (added by --generate" in text
    # The file --generate produces must pass the parser that will read it;
    # without the placeholder this rewrite produced an unparseable file.
    reparsed = parse_allowlist(path)
    assert reparsed.entries == ["fake.module::test_newly_broken"]


def test_vitest_generate_writes_a_todo_note_under_a_newly_measured_id(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "[vitest]",
        "version=2.1.9",
    )
    monkeypatch.setattr(check_vitest, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_vitest, "get_vitest_version", lambda: "2.1.9")
    report = _vitest_report(tmp_path, ["suite > newly broken"])

    code = _run(
        check_vitest, "--json-report", str(report), "--generate", "--reason", "stage 3 fallout"
    )
    assert code == 0
    assert "# ^ TODO: reason (added by --generate" in path.read_text(encoding="utf-8")
    assert parse_allowlist(path).entries == ["src/test/x.test.ts > suite > newly broken"]


def test_tsc_generate_writes_a_todo_note_under_a_newly_measured_path(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "[tsc-files]",
        "version=5.9.3",
        "baseline=0",
    )
    monkeypatch.setattr(check_tsc, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_tsc, "get_tsc_version", lambda: "5.9.3")
    log = _tsc_log(tmp_path, ["src/tools/new-thing.ts"])

    code = _run(check_tsc, "--tsc-log", str(log), "--generate", "--reason", "tsc 5.9.3 bump")
    assert code == 0

    section = parse_allowlist(path).sections["tsc-files"]
    assert section.lines == ["src/tools/new-thing.ts"]
    assert section.notes["src/tools/new-thing.ts"] == [
        f"# ^ TODO: reason (added by --generate {utc_today()})"
    ]


# ---------------------------------------------------------------------------
# --generate leaves a trail, and cannot assert a version it did not measure
# ---------------------------------------------------------------------------


def test_was_now_line_names_both_ends():
    assert was_now_line("baseline", "0.8.6", "200", "0.9.0", 212) == (
        "was: version=0.8.6 baseline=200 -> now: version=0.9.0 baseline=212"
    )


def test_was_now_line_says_none_when_there_was_no_previous_section():
    assert was_now_line("baseline", None, None, "0.8.6", 3) == (
        "was: version=none baseline=none -> now: version=0.8.6 baseline=3"
    )


def _report_for(module, tmp_path: Path) -> Path:
    if module is check_ruff:
        return _ruff_report(tmp_path, 0)
    if module is check_pytest:
        return _junit_xml(tmp_path, [])
    if module is check_vitest:
        return _vitest_report(tmp_path, [])
    return _tsc_log(tmp_path, [])


@pytest.mark.parametrize(
    "module,flag,version_getter,version",
    [
        (check_ruff, "--json-report", "get_ruff_version", "0.8.6"),
        (check_pytest, "--junit-xml", "get_pytest_version", "8.4.2"),
        (check_vitest, "--json-report", "get_vitest_version", "2.1.9"),
        (check_tsc, "--tsc-log", "get_tsc_version", "5.9.3"),
    ],
)
def test_generate_without_a_reason_exits_2(
    tmp_path: Path, monkeypatch, capsys, module, flag, version_getter, version
):
    path = _write(tmp_path / "known_failures.txt", "[ruff]", "version=0.8.6", "baseline=0")
    monkeypatch.setattr(module, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(module, version_getter, lambda: version)

    code = _run(module, flag, str(_report_for(module, tmp_path)), "--generate")

    out = capsys.readouterr().out
    # 2, not 1: a usage error, distinct from "the gate refused".
    assert code == 2
    assert "--reason" in out
    # A refused --generate writes nothing.
    assert "baseline=0" in path.read_text(encoding="utf-8")


def test_ruff_generate_records_the_reason_and_prints_was_now(tmp_path: Path, monkeypatch, capsys):
    path = _write(
        tmp_path / "known_failures.txt",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_ruff, "get_ruff_version", lambda: "0.8.6")
    report = _ruff_report(tmp_path, 190)

    code = _run(
        check_ruff, "--json-report", str(report), "--generate", "--reason", "paid down 10 E501s"
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "was: version=0.8.6 baseline=200 -> now: version=0.8.6 baseline=190" in out

    section = parse_allowlist(path).sections["ruff"]
    assert section.kv["regenerated"] == f"{utc_today()} paid down 10 E501s"


def test_generate_keeps_only_the_newest_regenerated_line(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path / "known_failures.txt",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_ruff, "get_ruff_version", lambda: "0.8.6")

    _run(
        check_ruff,
        "--json-report",
        str(_ruff_report(tmp_path, 190)),
        "--generate",
        "--reason",
        "first pass",
    )
    _run(
        check_ruff,
        "--json-report",
        str(_ruff_report(tmp_path, 180)),
        "--generate",
        "--reason",
        "second pass",
    )

    text = path.read_text(encoding="utf-8")
    # One line, not a growing log: the file records the current state, git
    # history holds the rest.
    assert text.count("regenerated=") == 1
    assert "second pass" in text
    assert "first pass" not in text


def test_another_tools_generate_neither_steals_nor_drops_a_regenerated_line(
    tmp_path: Path, monkeypatch
):
    path = _write(
        tmp_path / "known_failures.txt",
        "[pytest]",
        "version=8.4.2",
        "regenerated=2026-09-01 pytest 8.4.2 bump",
        "",
        "[ruff]",
        "version=0.8.6",
        "baseline=200",
    )
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_ruff, "get_ruff_version", lambda: "0.8.6")

    code = _run(
        check_ruff,
        "--json-report",
        str(_ruff_report(tmp_path, 190)),
        "--generate",
        "--reason",
        "ruff rerun",
    )
    assert code == 0

    sections = parse_allowlist(path).sections
    # Each section's regenerated= belongs to the tool that measured it.
    assert sections["pytest"].kv["regenerated"] == "2026-09-01 pytest 8.4.2 bump"
    assert sections["ruff"].kv["regenerated"] == f"{utc_today()} ruff rerun"


@pytest.mark.parametrize(
    "module,flag,version_getter,installed,claimed,tool",
    [
        (check_ruff, "--json-report", "get_ruff_version", "0.8.6", "0.16.7", "ruff"),
        (check_pytest, "--junit-xml", "get_pytest_version", "8.4.2", "9.0.0", "pytest"),
        (check_vitest, "--json-report", "get_vitest_version", "2.1.9", "3.0.0", "vitest"),
        (check_tsc, "--tsc-log", "get_tsc_version", "5.9.3", "6.0.0", "tsc"),
    ],
)
def test_generate_refuses_an_override_version_that_is_not_installed(
    tmp_path: Path, monkeypatch, capsys, module, flag, version_getter, installed, claimed, tool
):
    # The hole this closes: `--generate --override-version 0.16.7` used to
    # write version=0.16.7 into the file while ruff 0.8.6 did the measuring,
    # i.e. a baseline asserting a version that never ran.
    path = _write(tmp_path / "known_failures.txt", "[ruff]", "version=0.8.6", "baseline=0")
    monkeypatch.setattr(module, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(module, version_getter, lambda: installed)

    code = _run(
        module,
        flag,
        str(_report_for(module, tmp_path)),
        "--generate",
        "--reason",
        "x",
        "--override-version",
        claimed,
    )

    out = capsys.readouterr().out
    assert code == 1
    assert f"override-version {claimed}" in out
    assert f"installed {tool} {installed}" in out
    assert "may only carry the version that measured it" in out
    # Nothing was written: the refusal precedes the rewrite.
    assert path.read_text(encoding="utf-8").count("version=0.8.6") == 1


def test_generate_accepts_an_override_version_equal_to_the_installed_tool(
    tmp_path: Path, monkeypatch
):
    path = _write(tmp_path / "known_failures.txt", "[ruff]", "version=0.8.6", "baseline=200")
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    monkeypatch.setattr(check_ruff, "get_ruff_version", lambda: "0.8.6")

    code = _run(
        check_ruff,
        "--json-report",
        str(_ruff_report(tmp_path, 190)),
        "--generate",
        "--reason",
        "same version, fewer findings",
        "--override-version",
        "0.8.6",
    )
    assert code == 0
    assert parse_allowlist(path).sections["ruff"].kv["baseline"] == "190"


def test_override_version_still_simulates_a_mismatch_without_generate(tmp_path: Path, monkeypatch):
    # Outside --generate the flag keeps its original purpose: it is how the
    # version-mismatch gate itself is tested, and it writes nothing.
    path = _write(tmp_path / "known_failures.txt", "[ruff]", "version=0.8.6", "baseline=200")
    monkeypatch.setattr(check_ruff, "ALLOWLIST_PATH", path)
    code = _run(
        check_ruff,
        "--json-report",
        str(_ruff_report(tmp_path, 200)),
        "--override-version",
        "9.9.9",
    )
    assert code == 1
