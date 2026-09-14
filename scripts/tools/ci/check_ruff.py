#!/usr/bin/env python
"""CI gate for ruff.

Runs ``ruff check scripts/ --output-format=json`` and fails only if the
total number of findings grows past the ``baseline`` recorded under the
``[ruff]`` section of ``scripts/test/known_failures.txt``. This is a
simple count gate (not a per-finding allowlist like pytest/vitest): ruff's
~200 pre-existing findings are lint debt, not correctness bugs, so any
*new* finding pushing the count above the baseline fails the job, while
fixing some findings (dropping the count) is always fine.

The recorded baseline is only meaningful for the ruff version it was
measured with -- a ruff upgrade can add rules and inflate the finding
count with no code change at all. So the ``[ruff]`` section also records
``version=``, and this script fails outright (without comparing counts) if
the running ruff version doesn't match it. See check_tool_version in
_common.py.

Usage:
    uv run --no-sync python scripts/tools/ci/check_ruff.py
    uv run --no-sync python scripts/tools/ci/check_ruff.py --json-report path/to/report.json
    uv run --no-sync python scripts/tools/ci/check_ruff.py --generate
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
    check_tool_version,
    get_ruff_version,
    parse_allowlist,
    render_other_sections,
    run_cmd,
)

ALLOWLIST_PATH = REPO_ROOT / "scripts" / "test" / "known_failures.txt"


def run_ruff(json_report: Path) -> None:
    proc = run_cmd(
        ["uv", "run", "--no-sync", "ruff", "check", "scripts/", "--output-format=json"],
        check=False,  # ruff exits non-zero when there are findings; that's expected here
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    json_report.write_text(proc.stdout or "[]", encoding="utf-8")


def count_findings(json_report: Path) -> int:
    data = json.loads(json_report.read_text(encoding="utf-8"))
    return len(data)


def write_baseline(count: int, version: str) -> None:
    existing = parse_allowlist(ALLOWLIST_PATH)
    lines = list(existing.entries)
    lines.append("")
    lines.append("[ruff]")
    lines.append(f"version={version}")
    lines.append(f"baseline={count}")
    lines.extend(render_other_sections(existing.sections, skip={"ruff"}))
    ALLOWLIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="Use an existing `ruff check --output-format=json` report instead of running ruff.",
    )
    ap.add_argument(
        "--generate",
        action="store_true",
        help="Overwrite the [ruff] version + baseline with the current tool version and finding count.",
    )
    ap.add_argument(
        "--override-version",
        default=None,
        help=(
            "Use this string as the 'running' ruff version instead of actually "
            "invoking `ruff --version`. For testing the version-mismatch gate only."
        ),
    )
    args = ap.parse_args()

    if args.json_report is not None:
        json_report = args.json_report
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-ruff-"))
        json_report = tmp_dir / "ruff-report.json"
        run_ruff(json_report)

    count = count_findings(json_report)
    running_version = args.override_version or get_ruff_version()

    if args.generate:
        write_baseline(count, running_version)
        rel = ALLOWLIST_PATH.relative_to(REPO_ROOT)
        print(f"Wrote version={running_version} baseline={count} to {rel}")
        return 0

    allow = parse_allowlist(ALLOWLIST_PATH)
    section = allow.sections.get("ruff")
    rel = ALLOWLIST_PATH.relative_to(REPO_ROOT)

    version_error = check_tool_version(section, running_version, "ruff", str(rel))
    if version_error:
        print(version_error)
        return 1

    try:
        baseline = int(section.kv.get("baseline", "0")) if section else 0
    except ValueError:
        baseline = 0

    if count > baseline:
        print(f"ruff: {count} finding(s) exceeds recorded baseline={baseline}.")
        return 1

    if count < baseline:
        print(
            f"ruff: warning - only {count} finding(s), below recorded "
            f"baseline={baseline}; consider lowering the baseline."
        )

    print(f"ruff: {count} finding(s) (baseline {baseline}, version {running_version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
