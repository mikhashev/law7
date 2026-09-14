#!/usr/bin/env python
"""CI gate for vitest.

Runs the vitest suite (or reads an already-produced JSON report) and fails
only if a test fails that is NOT already listed in
``src/test/known_failures.txt``. Known failures stay silent; anything new
turns the job red. The gate is two-sided: an entry that is listed but no
longer failing (the test passes now, or was renamed/deleted) also turns the
job red, because a stale entry is a pre-issued permission for a future
failure -- whoever breaks that test next gets a green build.

A vitest upgrade can change collection/reporting behavior with no test
change at all, so the ``[vitest]`` section of the allowlist also records
``version=``, and this script fails outright (without comparing the known
failure ids) if the running vitest version doesn't match it. See
check_tool_version in _common.py.

Usage:
    npx vitest run --reporter=json --outputFile=... is invoked internally;
    or pass an existing report:
        python scripts/tools/ci/check_vitest.py --json-report path/to/report.json
        python scripts/tools/ci/check_vitest.py --generate
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REPO_ROOT,
    Allowlist,
    AllowlistError,
    check_tool_version,
    get_vitest_version,
    parse_allowlist,
    rel_to_repo,
    render_entries,
    render_other_sections,
    run_cmd,
)

ALLOWLIST_PATH = REPO_ROOT / "src" / "test" / "known_failures.txt"

HEADER = """\
# Stage 1 debt: get-statistics number-formatting assertions (Phase 7A).
#
# One vitest test id per line, ABOVE the [vitest] header (an id written
# under a section allowlists nothing), formatted as:
#   relative/path/to/file.test.ts > describe block > ... > it name
# A whole line starting with '#' is a comment; an inline '#' is rejected.
# Attach the required issue/stage note on the line directly below the id:
#   src/test/x.test.ts > suite > it name
#   # ^ broken since migration 003, see audit/PLAN stage 3
# Notes are carried forward by --generate and dropped with their id.
# Remove an entry when the test is fixed; never add an entry without a
# linked issue/stage note. See scripts/tools/ci/README.md.
"""


def run_vitest(json_report: Path) -> None:
    run_cmd(
        [
            "npx",
            "vitest",
            "run",
            "--reporter=default",
            "--reporter=json",
            f"--outputFile={json_report}",
        ],
        check=False,  # vitest exits non-zero when tests fail; that's expected here
    )


def to_relative(path_str: str) -> str:
    try:
        return Path(path_str).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path_str.replace("\\", "/")


def parse_failures(json_report: Path) -> list[str]:
    data = json.loads(json_report.read_text(encoding="utf-8"))
    ids = set()
    for suite in data.get("testResults", []):
        rel = to_relative(suite.get("name", ""))
        for assertion in suite.get("assertionResults", []):
            if assertion.get("status") == "failed":
                full_name = assertion.get("fullName") or assertion.get("title", "")
                ids.add(f"{rel} > {full_name}")
    return sorted(ids)


def write_allowlist(failures: list[str], version: str, existing: Allowlist) -> None:
    lines = [HEADER.rstrip("\n")]
    if failures:
        lines.append("")
        # Notes ride along with the ids that survive; a note whose id is no
        # longer failing disappears together with that id.
        lines.extend(render_entries(failures, existing.notes))
    lines.append("")
    lines.append("[vitest]")
    lines.append(f"version={version}")
    lines.extend(render_other_sections(existing.sections, skip={"vitest"}))
    ALLOWLIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="Use an existing vitest --reporter=json report instead of running vitest.",
    )
    ap.add_argument(
        "--generate",
        action="store_true",
        help="Overwrite the allowlist with the current tool version and currently failing tests.",
    )
    ap.add_argument(
        "--override-version",
        default=None,
        help=(
            "Use this string as the 'running' vitest version instead of actually "
            "invoking `vitest --version`. For testing the version-mismatch gate only."
        ),
    )
    args = ap.parse_args()

    rel = rel_to_repo(ALLOWLIST_PATH)
    try:
        allow = parse_allowlist(ALLOWLIST_PATH)
    except AllowlistError as exc:
        print(f"vitest: malformed allowlist: {exc}")
        return 1

    if args.json_report is not None:
        json_report = args.json_report
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-vitest-"))
        json_report = tmp_dir / "vitest-report.json"
        run_vitest(json_report)

    failures = parse_failures(json_report)
    running_version = args.override_version or get_vitest_version()

    if args.generate:
        write_allowlist(failures, running_version, allow)
        print(f"Wrote version={running_version} and {len(failures)} entries to {rel}")
        return 0

    version_error = check_tool_version(
        allow.sections.get("vitest"), running_version, "vitest", str(rel)
    )
    if version_error:
        print(version_error)
        return 1

    allowed = set(allow.entries)
    failing = set(failures)

    new_failures = sorted(failing - allowed)
    stale = sorted(allowed - failing)

    if new_failures:
        print(f"vitest: {len(new_failures)} failure(s) not in {rel}:")
        for item in new_failures:
            print(f"  {item}")
        return 1

    if stale:
        print(
            f"vitest: {len(stale)} stale allowlist entry(ies) in {rel} "
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

    print(f"vitest: {len(failing)} known failure(s), all allowlisted (version {running_version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
