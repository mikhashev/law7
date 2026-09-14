#!/usr/bin/env python
"""CI gate for ruff.

Runs ``ruff check scripts/ --output-format=json`` and fails only if the
total number of findings grows past the ``ruff_baseline`` recorded under
the ``[ruff]`` section of ``scripts/test/known_failures.txt``. This is a
simple count gate (not a per-finding allowlist like pytest/vitest): ruff's
~200 pre-existing findings are lint debt, not correctness bugs, so any
*new* finding pushing the count above the baseline fails the job, while
fixing some findings (dropping the count) is always fine.

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
from _common import REPO_ROOT, parse_allowlist, run_cmd  # noqa: E402

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


def write_baseline(count: int) -> None:
    existing = parse_allowlist(ALLOWLIST_PATH)
    lines = list(existing.entries)
    lines.append("")
    lines.append("[ruff]")
    lines.append(f"ruff_baseline={count}")
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
        help="Overwrite the [ruff] baseline with the current finding count.",
    )
    args = ap.parse_args()

    if args.json_report is not None:
        json_report = args.json_report
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-ruff-"))
        json_report = tmp_dir / "ruff-report.json"
        run_ruff(json_report)

    count = count_findings(json_report)

    if args.generate:
        write_baseline(count)
        rel = ALLOWLIST_PATH.relative_to(REPO_ROOT)
        print(f"Wrote ruff_baseline={count} to {rel}")
        return 0

    allow = parse_allowlist(ALLOWLIST_PATH)
    section = allow.sections.get("ruff")
    try:
        baseline = int(section.kv.get("ruff_baseline", "0")) if section else 0
    except ValueError:
        baseline = 0

    if count > baseline:
        print(f"ruff: {count} finding(s) exceeds recorded ruff_baseline={baseline}.")
        return 1

    if count < baseline:
        print(
            f"ruff: warning - only {count} finding(s), below recorded "
            f"ruff_baseline={baseline}; consider lowering the baseline."
        )

    print(f"ruff: {count} finding(s) (baseline {baseline}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
