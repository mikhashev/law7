#!/usr/bin/env python
"""CI gate for pytest.

Runs the pytest suite (or reads an already-produced JUnit XML report) and
fails only if a test fails/errors that is NOT already listed in
``scripts/test/known_failures.txt``. Known failures stay silent; anything
new turns the job red. Allowlist entries that now pass are reported as a
warning (stale allowlist) but do not fail the job.

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
from _common import REPO_ROOT, parse_allowlist, run_cmd  # noqa: E402

ALLOWLIST_PATH = REPO_ROOT / "scripts" / "test" / "known_failures.txt"

HEADER = """\
# Stage 1 debt: mocks target Phase 7A shim modules
#
# One pytest node id (file::Class::test or file::test) per line.
# '#' starts a comment. Remove an entry when the test is fixed; never add an
# entry without a linked issue/stage note. See scripts/tools/ci/README.md.
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


def write_allowlist(failures: list[str]) -> None:
    lines = [HEADER.rstrip("\n"), ""]
    lines.extend(failures)
    existing = parse_allowlist(ALLOWLIST_PATH)
    ruff_section = existing.sections.get("ruff")
    if ruff_section is not None:
        lines.append("")
        lines.append("[ruff]")
        for key, value in ruff_section.kv.items():
            lines.append(f"{key}={value}")
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
        help="Overwrite the allowlist with the currently failing/erroring tests.",
    )
    args = ap.parse_args()

    if args.junit_xml is not None:
        junit_xml = args.junit_xml
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-pytest-"))
        junit_xml = tmp_dir / "pytest-report.xml"
        run_pytest(junit_xml)

    failures = parse_failures(junit_xml)

    if args.generate:
        write_allowlist(failures)
        print(f"Wrote {len(failures)} entries to {ALLOWLIST_PATH.relative_to(REPO_ROOT)}")
        return 0

    allow = parse_allowlist(ALLOWLIST_PATH)
    allowed = set(allow.entries)
    failing = set(failures)

    new_failures = sorted(failing - allowed)
    stale = sorted(allowed - failing)

    if new_failures:
        rel = ALLOWLIST_PATH.relative_to(REPO_ROOT)
        print(f"pytest: {len(new_failures)} failure(s) not in {rel}:")
        for item in new_failures:
            print(f"  {item}")
        return 1

    if stale:
        print(
            f"pytest: warning - {len(stale)} allowlisted test(s) now pass; remove from allowlist:"
        )
        for item in stale:
            print(f"  {item}")

    print(f"pytest: {len(failing)} known failure(s), all allowlisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
