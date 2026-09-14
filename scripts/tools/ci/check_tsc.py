#!/usr/bin/env python
"""CI gate for the TypeScript compiler.

``npm run build`` (``tsc``) still emits ``dist/`` even when it exits
non-zero, so the CI build step runs the compiler itself and this script
separately decides whether the result is acceptable: errors are only
tolerated in the files listed under the ``[tsc-files]`` section of
``src/test/known_failures.txt``, and only up to the recorded
``tsc_baseline`` count. Any error in another file, or a total count above
the baseline, fails the job; a total at or below the baseline (even if some
listed files have since been fixed) does not.

Usage:
    npx tsc --noEmit -p . --pretty false is invoked internally; or pass an
    existing compiler log:
        python scripts/tools/ci/check_tsc.py --tsc-log path/to/log.txt
        python scripts/tools/ci/check_tsc.py --generate
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, parse_allowlist, run_cmd  # noqa: E402

ALLOWLIST_PATH = REPO_ROOT / "src" / "test" / "known_failures.txt"

# "src/test/tools/get-code-structure.test.ts(117,52): error TS2345: ..."
ERROR_LINE_RE = re.compile(r"^(?P<file>[^(].*?)\((?P<line>\d+),(?P<col>\d+)\): error TS\d+:")


def run_tsc(log_path: Path) -> None:
    proc = run_cmd(
        ["npx", "tsc", "--noEmit", "-p", ".", "--pretty", "false"],
        check=False,  # tsc exits non-zero when there are errors; that's expected here
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log_path.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")


def parse_errors(log_path: Path) -> list[str]:
    """Return the relative file path (posix) for each ``error TS####`` line."""
    text = log_path.read_text(encoding="utf-8")
    files = []
    for raw_line in text.splitlines():
        match = ERROR_LINE_RE.match(raw_line.strip())
        if match:
            files.append(match.group("file").strip().replace("\\", "/"))
    return files


def write_allowlist(error_files: list[str], baseline: int) -> None:
    """Rewrite the ``[tsc-files]`` section in place, preserving the vitest
    preamble entries that check_vitest.py --generate already wrote (comment
    headers are not preserved by the parser, so run check_vitest.py's
    --generate first if a fresh header is wanted).
    """
    existing = parse_allowlist(ALLOWLIST_PATH)
    lines = list(existing.entries)
    lines.append("")
    lines.append("[tsc-files]")
    for f in sorted(set(error_files)):
        lines.append(f)
    lines.append(f"tsc_baseline={baseline}")
    ALLOWLIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--tsc-log",
        type=Path,
        default=None,
        help="Use an existing `tsc --noEmit --pretty false` text log instead of running tsc.",
    )
    ap.add_argument(
        "--generate",
        action="store_true",
        help="Overwrite the [tsc-files] section with the currently erroring files/count.",
    )
    args = ap.parse_args()

    if args.tsc_log is not None:
        log_path = args.tsc_log
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-tsc-"))
        log_path = tmp_dir / "tsc.log"
        run_tsc(log_path)

    error_files = parse_errors(log_path)
    total = len(error_files)

    if args.generate:
        write_allowlist(error_files, total)
        rel = ALLOWLIST_PATH.relative_to(REPO_ROOT)
        print(f"Wrote {len(set(error_files))} file(s), tsc_baseline={total}, to {rel}")
        return 0

    allow = parse_allowlist(ALLOWLIST_PATH)
    section = allow.sections.get("tsc-files")
    allowed_files = set(section.lines) if section else set()
    try:
        baseline = int(section.kv.get("tsc_baseline", "0")) if section else 0
    except ValueError:
        baseline = 0

    outside_allowlist = sorted({f for f in error_files if f not in allowed_files})

    if outside_allowlist:
        rel = ALLOWLIST_PATH.relative_to(REPO_ROOT)
        print(f"tsc: error(s) in file(s) not listed under [tsc-files] in {rel}:")
        for f in outside_allowlist:
            print(f"  {f}")
        return 1

    if total > baseline:
        print(f"tsc: {total} error(s) exceeds recorded tsc_baseline={baseline}.")
        return 1

    if total < baseline:
        print(
            f"tsc: warning - only {total} error(s) found, below recorded "
            f"tsc_baseline={baseline}; consider lowering the baseline."
        )

    print(f"tsc: {total} known error(s) (baseline {baseline}), all in allowlisted files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
