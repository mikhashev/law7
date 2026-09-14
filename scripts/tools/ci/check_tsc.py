#!/usr/bin/env python
"""CI gate for the TypeScript compiler.

``npm run build`` (``tsc``) still emits ``dist/`` even when it exits
non-zero, so the CI build step runs the compiler itself and this script
separately decides whether the result is acceptable: errors are only
tolerated in the files listed under the ``[tsc-files]`` section of
``src/test/known_failures.txt``, and only up to the recorded ``baseline``
count. Any error in another file, or a total count above the baseline,
fails the job; a total at or below the baseline (even if some listed files
have since been fixed) does not.

The recorded baseline is only meaningful for the tsc version it was
measured with -- a compiler upgrade can start flagging previously-legal
code with no source change at all. So ``[tsc-files]`` also records
``version=``, and this script fails outright (without comparing counts) if
the running tsc version doesn't match it. See check_tool_version in
_common.py.

Every allowlisted file path carries a ``# ^`` note naming the issue or stage
that explains it; a path without one is a parse error, not a style nit.

``--generate`` leaves a trail: it requires ``--reason "<text>"``, prints the
was -> now delta, and records ``regenerated=<date> <reason>`` in the
``[tsc-files]`` section. It also refuses a ``--override-version`` that
differs from the installed tsc, so a baseline can never claim a version that
did not measure it.

Usage:
    npx tsc --noEmit -p . --pretty false is invoked internally; or pass an
    existing compiler log:
        python scripts/tools/ci/check_tsc.py --tsc-log path/to/log.txt
        python scripts/tools/ci/check_tsc.py --generate --reason "why"
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REGENERATED_KEY,
    REPO_ROOT,
    Allowlist,
    AllowlistError,
    check_generate_args,
    check_tool_version,
    fill_missing_notes,
    get_tsc_version,
    parse_allowlist,
    regenerated_value,
    rel_to_repo,
    render_entries,
    render_other_sections,
    run_cmd,
    was_now_line,
)

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


def write_allowlist(
    error_files: list[str], baseline: int, version: str, reason: str, existing: Allowlist
) -> None:
    """Rewrite the ``[tsc-files]`` section in place, preserving the vitest
    preamble entries that check_vitest.py --generate already wrote, with
    their ``# ^`` notes (plain comment headers are not preserved by the
    parser, so run check_vitest.py's --generate first if a fresh header is
    wanted).

    ``[tsc-files]`` is the one section whose bare lines are data, so its
    file paths are entries like any other: each one needs a ``# ^`` note, a
    note for a file that no longer errors is dropped along with the path, and
    a newly measured path gets the TODO placeholder so the generated file
    passes its own parser.
    """
    lines = render_entries(existing.entries, existing.notes)
    section = existing.sections.get("tsc-files")
    file_notes = section.notes if section else {}
    paths = sorted(set(error_files))
    lines.append("")
    lines.append("[tsc-files]")
    lines.append(f"version={version}")
    lines.extend(render_entries(paths, fill_missing_notes(paths, file_notes)))
    lines.append(f"baseline={baseline}")
    lines.append(f"{REGENERATED_KEY}={regenerated_value(reason)}")
    lines.extend(render_other_sections(existing.sections, skip={"tsc-files"}))
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
        help="Overwrite the [tsc-files] section with the current tool version and erroring files/count.",
    )
    ap.add_argument(
        "--reason",
        default=None,
        help=(
            "Why the baseline is being regenerated. Required with --generate; "
            "recorded in the [tsc-files] section as `regenerated=<date> <reason>`."
        ),
    )
    ap.add_argument(
        "--override-version",
        default=None,
        help=(
            "Use this string as the 'running' tsc version instead of actually "
            "invoking `tsc --version`. For testing the version-mismatch gate only; "
            "with --generate it must equal the installed tsc."
        ),
    )
    args = ap.parse_args()

    rel = rel_to_repo(ALLOWLIST_PATH)
    try:
        allow = parse_allowlist(ALLOWLIST_PATH)
    except AllowlistError as exc:
        print(f"tsc: malformed allowlist: {exc}")
        return 1

    if args.tsc_log is not None:
        log_path = args.tsc_log
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-tsc-"))
        log_path = tmp_dir / "tsc.log"
        run_tsc(log_path)

    error_files = parse_errors(log_path)
    total = len(error_files)
    running_version = args.override_version or get_tsc_version()
    section = allow.sections.get("tsc-files")

    if args.generate:
        refusal = check_generate_args(args.reason, args.override_version, "tsc", get_tsc_version)
        if refusal:
            message, code = refusal
            print(message)
            return code
        old_version = section.kv.get("version") if section else None
        old_baseline = section.kv.get("baseline") if section else None
        print(was_now_line("baseline", old_version, old_baseline, running_version, total))
        write_allowlist(error_files, total, running_version, args.reason, allow)
        print(
            f"Wrote version={running_version}, {len(set(error_files))} file(s), "
            f"baseline={total}, to {rel}"
        )
        return 0

    version_error = check_tool_version(section, running_version, "tsc", str(rel))
    if version_error:
        print(version_error)
        return 1

    # `lines` holds every non-key=value entry under [tsc-files], i.e. the
    # allowlisted file paths (version= and baseline= are parsed into `kv`).
    allowed_files = set(section.lines) if section else set()
    try:
        baseline = int(section.kv.get("baseline", "0")) if section else 0
    except ValueError:
        baseline = 0

    outside_allowlist = sorted({f for f in error_files if f not in allowed_files})

    if outside_allowlist:
        print(f"tsc: error(s) in file(s) not listed under [tsc-files] in {rel}:")
        for f in outside_allowlist:
            print(f"  {f}")
        return 1

    if total > baseline:
        print(f"tsc: {total} error(s) exceeds recorded baseline={baseline}.")
        return 1

    if total < baseline:
        print(
            f"tsc: warning - only {total} error(s) found, below recorded "
            f"baseline={baseline}; consider lowering the baseline."
        )

    print(
        f"tsc: {total} known error(s) (baseline {baseline}, version {running_version}), "
        "all in allowlisted files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
