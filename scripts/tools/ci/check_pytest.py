#!/usr/bin/env python
"""CI gate for pytest.

Runs the pytest suite (or reads an already-produced JUnit XML report) and
fails only if a test fails/errors that is NOT already listed in
``scripts/test/known_failures.txt``. Known failures stay silent; anything
new turns the job red. The gate is two-sided: an entry that is listed but
no longer failing (the test passes now, or was renamed/deleted) also turns
the job red, because a stale entry is a pre-issued permission for a future
failure -- whoever breaks that test next gets a green build.

A pytest upgrade can change collection/reporting behavior with no test
change at all, so the ``[pytest]`` section of the allowlist also records
``version=``, and this script fails outright (without comparing the known
failure ids) if the running pytest version doesn't match it. See
check_tool_version in _common.py.

Usage:
    uv run --no-sync python scripts/tools/ci/check_pytest.py
    uv run --no-sync python scripts/tools/ci/check_pytest.py --junit-xml path/to/report.xml
    uv run --no-sync python scripts/tools/ci/check_pytest.py --generate
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REPO_ROOT,
    Allowlist,
    AllowlistError,
    check_tool_version,
    get_pytest_version,
    parse_allowlist,
    rel_to_repo,
    render_entries,
    render_other_sections,
    run_cmd,
)

ALLOWLIST_PATH = REPO_ROOT / "scripts" / "test" / "known_failures.txt"

HEADER = """\
# Stage 1 debt: mocks target Phase 7A shim modules
#
# One pytest node id (file::Class::test or file::test) per line, ABOVE the
# [pytest] header -- an id written under a section allowlists nothing.
# A whole line starting with '#' is a comment; an inline '#' is rejected.
# Attach the required issue/stage note on the line directly below the id:
#   scripts/test/x.py::test_y
#   # ^ broken since migration 003, see audit/PLAN stage 3
# Notes are carried forward by --generate and dropped with their id.
# Remove an entry when the test is fixed; never add an entry without a
# linked issue/stage note. See scripts/tools/ci/README.md.
"""


def run_pytest(junit_xml: Path) -> None:
    run_cmd(
        ["uv", "run", "--no-sync", "pytest", "-q", f"--junitxml={junit_xml}"],
        check=False,  # pytest exits non-zero when tests fail; that's expected here
    )


def testcase_id(classname: str, name: str) -> str:
    """Turn a JUnit ``classname`` (dotted module[.Class[.NestedClass]]) plus
    ``name`` into a pytest node id: ``path/to/file.py::Class::test_name``.

    JUnit XML from pytest does not carry the source file path directly, so
    this walks the dotted classname from the longest prefix down, looking
    for a prefix that matches a real ``.py`` file on disk. Whatever dotted
    segments remain after that prefix are the (possibly nested) class name.
    """
    parts = classname.split(".")
    for split_at in range(len(parts), 0, -1):
        candidate = REPO_ROOT.joinpath(*parts[:split_at]).with_suffix(".py")
        if candidate.is_file():
            file_part = "/".join(parts[:split_at]) + ".py"
            class_parts = parts[split_at:]
            return "::".join([file_part, *class_parts, name])
    # Could not resolve to a real file (e.g. unusual layout); fall back to
    # the raw classname so the id is still stable and greppable.
    return f"{classname}::{name}"


def parse_failures(junit_xml: Path) -> list[str]:
    tree = ET.parse(junit_xml)
    ids = set()
    for testcase in tree.getroot().iter("testcase"):
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            classname = testcase.get("classname", "")
            name = testcase.get("name", "")
            ids.add(testcase_id(classname, name))
    return sorted(ids)


def write_allowlist(failures: list[str], version: str, existing: Allowlist) -> None:
    lines = [HEADER.rstrip("\n")]
    if failures:
        lines.append("")
        # Notes ride along with the ids that survive; a note whose id is no
        # longer failing disappears together with that id.
        lines.extend(render_entries(failures, existing.notes))
    lines.append("")
    lines.append("[pytest]")
    lines.append(f"version={version}")
    lines.extend(render_other_sections(existing.sections, skip={"pytest"}))
    ALLOWLIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--junit-xml",
        type=Path,
        default=None,
        help="Use an existing JUnit XML report instead of running pytest.",
    )
    ap.add_argument(
        "--generate",
        action="store_true",
        help="Overwrite the allowlist with the current tool version and failing/erroring tests.",
    )
    ap.add_argument(
        "--override-version",
        default=None,
        help=(
            "Use this string as the 'running' pytest version instead of actually "
            "invoking `pytest --version`. For testing the version-mismatch gate only."
        ),
    )
    args = ap.parse_args()

    rel = rel_to_repo(ALLOWLIST_PATH)
    try:
        allow = parse_allowlist(ALLOWLIST_PATH)
    except AllowlistError as exc:
        print(f"pytest: malformed allowlist: {exc}")
        return 1

    if args.junit_xml is not None:
        junit_xml = args.junit_xml
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-pytest-"))
        junit_xml = tmp_dir / "pytest-report.xml"
        run_pytest(junit_xml)

    failures = parse_failures(junit_xml)
    running_version = args.override_version or get_pytest_version()

    if args.generate:
        write_allowlist(failures, running_version, allow)
        print(f"Wrote version={running_version} and {len(failures)} entries to {rel}")
        return 0

    version_error = check_tool_version(
        allow.sections.get("pytest"), running_version, "pytest", str(rel)
    )
    if version_error:
        print(version_error)
        return 1

    allowed = set(allow.entries)
    failing = set(failures)

    new_failures = sorted(failing - allowed)
    stale = sorted(allowed - failing)

    if new_failures:
        print(f"pytest: {len(new_failures)} failure(s) not in {rel}:")
        for item in new_failures:
            print(f"  {item}")
        return 1

    if stale:
        print(
            f"pytest: {len(stale)} stale allowlist entry(ies) in {rel} "
            f"(the test passes now, or no longer exists):"
        )
        for item in stale:
            print(f"  {item}")
        print(
            "A stale entry is a pre-issued permission for a future failure: it "
            "keeps the build green for whoever breaks that test next. "
            f"Remove it from {rel} (or re-measure with --generate)."
        )
        return 1

    print(f"pytest: {len(failing)} known failure(s), all allowlisted (version {running_version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
