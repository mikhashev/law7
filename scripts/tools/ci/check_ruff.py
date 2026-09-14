#!/usr/bin/env python
"""CI gate for ruff.

Runs ``ruff check scripts/ --output-format=json`` and fails only if the
total number of findings grows past the ``baseline`` recorded under the
``[ruff]`` section of ``scripts/test/known_failures.txt``. This is a
simple count gate (not a per-finding allowlist like pytest/vitest): ruff's
~200 pre-existing findings are lint debt, not correctness bugs, so any
*new* finding pushing the count above the baseline fails the job.

The gate is two-sided: a count *below* the baseline fails as well. A
baseline left above the real number is silent headroom -- it pre-approves
that many future findings -- so paying debt down means lowering the
baseline in the same commit that pays it. Being a count and not a
fingerprint, this gate measures volume, not composition (see
scripts/tools/ci/README.md).

The recorded baseline is only meaningful for the ruff version it was
measured with -- a ruff upgrade can add rules and inflate the finding
count with no code change at all. So the ``[ruff]`` section also records
``version=``, and this script fails outright (without comparing counts) if
the running ruff version doesn't match it. See check_tool_version in
_common.py.

``--generate`` leaves a trail: it requires ``--reason "<text>"``, prints the
was -> now delta, and records ``regenerated=<date> <reason>`` in the
``[ruff]`` section. It also refuses a ``--override-version`` that differs
from the installed ruff, so a baseline can never claim a version that did
not measure it.

Usage:
    uv run --no-sync python scripts/tools/ci/check_ruff.py
    uv run --no-sync python scripts/tools/ci/check_ruff.py --json-report path/to/report.json
    uv run --no-sync python scripts/tools/ci/check_ruff.py --generate --reason "why"
"""
from __future__ import annotations

import argparse
import json
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
    get_ruff_version,
    parse_allowlist,
    regenerated_value,
    rel_to_repo,
    render_entries,
    render_other_sections,
    run_cmd,
    was_now_line,
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


def write_baseline(count: int, version: str, reason: str, existing: Allowlist) -> None:
    # The pytest node ids (and their "# ^" notes) live in the same file, above
    # the first section header; carry them through untouched.
    lines = render_entries(existing.entries, existing.notes)
    lines.append("")
    lines.append("[ruff]")
    lines.append(f"version={version}")
    lines.append(f"baseline={count}")
    # Exactly one regenerated= line: the newest. Any previous one lived in the
    # [ruff] section this function rewrites, so it is replaced rather than
    # appended to -- the file records the current state, git history the log.
    lines.append(f"{REGENERATED_KEY}={regenerated_value(reason)}")
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
        "--reason",
        default=None,
        help=(
            "Why the baseline is being regenerated. Required with --generate; "
            "recorded in the [ruff] section as `regenerated=<date> <reason>`."
        ),
    )
    ap.add_argument(
        "--override-version",
        default=None,
        help=(
            "Use this string as the 'running' ruff version instead of actually "
            "invoking `ruff --version`. For testing the version-mismatch gate only; "
            "with --generate it must equal the installed ruff."
        ),
    )
    args = ap.parse_args()

    rel = rel_to_repo(ALLOWLIST_PATH)
    try:
        allow = parse_allowlist(ALLOWLIST_PATH)
    except AllowlistError as exc:
        print(f"ruff: malformed allowlist: {exc}")
        return 1

    if args.json_report is not None:
        json_report = args.json_report
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="law7-ruff-"))
        json_report = tmp_dir / "ruff-report.json"
        run_ruff(json_report)

    count = count_findings(json_report)
    running_version = args.override_version or get_ruff_version()
    section = allow.sections.get("ruff")

    if args.generate:
        refusal = check_generate_args(args.reason, args.override_version, "ruff", get_ruff_version)
        if refusal:
            message, code = refusal
            print(message)
            return code
        old_version = section.kv.get("version") if section else None
        old_baseline = section.kv.get("baseline") if section else None
        print(was_now_line("baseline", old_version, old_baseline, running_version, count))
        write_baseline(count, running_version, args.reason, allow)
        print(f"Wrote version={running_version} baseline={count} to {rel}")
        return 0

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
            f"ruff findings fell to {count}, baseline is {baseline} - lower the "
            f"baseline in the same commit "
            f'(uv run python scripts/tools/ci/check_ruff.py --generate --reason "<why>")'
        )
        return 1

    print(f"ruff: {count} finding(s) (baseline {baseline}, version {running_version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
