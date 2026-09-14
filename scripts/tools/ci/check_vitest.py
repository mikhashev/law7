#!/usr/bin/env python
"""CI gate for vitest.

Runs the vitest suite (or reads an already-produced JSON report) and fails
only if a test fails that is NOT already listed in
``src/test/known_failures.txt``. Known failures stay silent; anything new
turns the job red. Allowlist entries that now pass are reported as a
warning (stale allowlist) but do not fail the job.

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
from _common import REPO_ROOT, parse_allowlist, run_cmd  # noqa: E402

ALLOWLIST_PATH = REPO_ROOT / "src" / "test" / "known_failures.txt"

HEADER = """\
# Stage 1 debt: get-statistics number-formatting assertions (Phase 7A).
#
# One vitest test id per line, formatted as:
#   relative/path/to/file.test.ts > describe block > ... > it name
# '#' starts a comment. Remove an entry when the test is fixed; never add an
# entry without a linked issue/stage note. See scripts/tools/ci/README.md.
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


def write_allowlist(failures: list[str]) -> None:
    lines = [HEADER.rstrip("\n"), ""]
    lines.extend(failures)
    existing = parse_allowlist(ALLOWLIST_PATH)
    tsc_section = existing.sections.get("tsc-files")
    if tsc_section is not None:
        lines.append("")
        lines.append("[tsc-files]")
        for file_line in tsc_section.lines:
            lines.append(file_line)
        for key, value in tsc_section.kv.items():
            lines.append(f"{key}={value}")
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
        help="Overwrite the allowlist with the currently failing tests.",
    )
    args = ap.parse_args()

    if args.json_report is not None:
        json_report = args.json_report
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-vitest-"))
        json_report = tmp_dir / "vitest-report.json"
        run_vitest(json_report)

    failures = parse_failures(json_report)

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
        print(f"vitest: {len(new_failures)} failure(s) not in {rel}:")
        for item in new_failures:
            print(f"  {item}")
        return 1

    if stale:
        print(
            f"vitest: warning - {len(stale)} allowlisted test(s) now pass; remove from allowlist:"
        )
        for item in stale:
            print(f"  {item}")

    print(f"vitest: {len(failing)} known failure(s), all allowlisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
