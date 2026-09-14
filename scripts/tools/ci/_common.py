"""Shared helpers for the CI gate scripts in this directory.

Kept dependency-free (stdlib only) so these scripts can run with either
``uv run --no-sync python ...`` (Python job) or a plain system ``python``
(Node job, which does not sync the project's Python environment).
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

# scripts/tools/ci/_common.py -> repo root is three parents up.
REPO_ROOT = Path(__file__).resolve().parents[3]


def run_cmd(cmd: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
    """Run an external tool (npx, uv, ...) portably on Windows and Linux.

    On Windows, wrapper scripts installed by npm (npx.cmd) and similar are
    not directly executable via CreateProcess, so a plain ``subprocess.run``
    with ``shell=False`` raises FileNotFoundError even though the command
    works fine from a shell. Using ``shell=True`` there (and only there)
    resolves it; POSIX runners don't need it.
    """
    kwargs.setdefault("cwd", REPO_ROOT)
    return subprocess.run(list(cmd), shell=(sys.platform == "win32"), **kwargs)


# A note line attaches to the entry (node id / file path) on the line
# directly above it, so an allowlist entry can carry the "linked issue/stage
# note" the headers demand without inventing a second file:
#
#     scripts/test/x.py::test_y
#     # ^ broken since migration 003, see audit/PLAN stage 3
#
# A plain "# ..." line is still just a comment and attaches to nothing.
#
# The note is REQUIRED, not decorative: an entry with no "# ^" line directly
# below it is an AllowlistError. The headers have always said "never add an
# entry without a linked issue/stage note", but only the reverse (a note with
# no entry) was actually checked, so the rule was advice. An allowance nobody
# can trace back to an issue or stage is an allowance nobody ever retires.
NOTE_PREFIX = "# ^"

# What --generate writes under a freshly measured id that has no note yet, so
# that the file it produces passes this parser. It is a placeholder, not a
# note: the README requires replacing it with a real issue/stage reference
# before the commit.
TODO_NOTE_TEMPLATE = "# ^ TODO: reason (added by --generate {date})"

# Only [tsc-files] uses bare lines as data (the allowlisted file paths).
# Under every other section a bare line is a typo -- most dangerously a node
# id written below its [pytest] header instead of above it, where it would be
# silently ignored rather than allowlisting anything -- so it is rejected.
FREE_LINE_SECTIONS = frozenset({"tsc-files"})


class AllowlistError(Exception):
    """A known_failures.txt file could not be parsed.

    Raised instead of guessing, because every ambiguity here fails open: a
    misplaced node id allowlists nothing, an inline "# note" makes an id
    match nothing, so the gate would go green for the wrong reason. Callers
    print the message and exit 1.
    """


@dataclass
class Section:
    name: str
    kv: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)
    notes: dict = field(default_factory=dict)  # line -> ["# ^ ..."] note lines


@dataclass
class Allowlist:
    entries: list  # preamble plain entries, in file order, before any [section]
    sections: dict  # section name -> Section
    notes: dict = field(default_factory=dict)  # entry -> ["# ^ ..."] note lines


def _reject_inline_comment(line: str, where: str) -> None:
    if "#" in line:
        bare = line.split("#")[0].strip()
        raise AllowlistError(
            f"{where}: entry {line!r} contains an inline '#'. Inline comments are "
            f"not part of the format -- the whole line is the id/path, '#' and all, "
            f"so it would match nothing. Put the note on the next line instead: "
            f"{bare!r} on one line, then '# ^ your note here' on the next."
        )


def parse_allowlist(path: Path) -> Allowlist:
    """Parse a known_failures.txt file.

    Format:
        # comment (ignored)
        <plain entry>            # e.g. a pytest node id or vitest test name
        # ^ note about the entry directly above
        ...
        [section-name]
        key=value
        <plain entry within the section>   # e.g. a file path for [tsc-files]

    Entries before the first ``[section]`` header are returned in
    ``entries``; the file is UTF-8 and tolerant of CRLF or LF line endings
    (``str.splitlines`` handles both).

    Position is meaning: an entry belongs to the preamble only if it is
    written *before* the first ``[section]`` header. Under a section only
    ``key=value`` lines are read, except ``[tsc-files]`` where the bare
    lines are the data.

    A line starting with ``# ^`` is a note attached to the entry on the line
    directly above it: it is kept out of ``entries``/``lines`` and returned
    in ``notes`` so ``--generate`` can carry it forward with its entry. Every
    entry must have one.

    Raises ``AllowlistError`` on a note with nothing above it to attach to,
    an entry with no note below it, an entry with an inline ``#``, or a bare
    line under a section that only takes ``key=value``.
    """
    entries: list = []
    notes: dict = {}
    sections: dict = {}
    current: Section | None = None
    # The entry written on the previous line as (where, entry, note list), or
    # None if the previous line was anything else (blank, comment, header,
    # key=value). An entry stays pending only until the next line settles
    # whether it got its note.
    pending: tuple | None = None

    def close(pending_entry: tuple | None) -> None:
        """Fail if the entry that just ended never got a ``# ^`` note."""
        if pending_entry is None or pending_entry[2]:
            return
        entry_where, entry, _ = pending_entry
        raise AllowlistError(
            f"{entry_where}: entry {entry!r} has no note; add "
            f"`# ^ <issue or stage note>` on the next line. Every allowlisted "
            f"failure has to name the issue or stage that explains it -- an "
            f"allowance nobody can trace back is one nobody ever retires."
        )

    if not path.exists():
        return Allowlist(entries=entries, sections=sections, notes=notes)
    text = path.read_text(encoding="utf-8")
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        where = f"{path}:{lineno}"
        if line.startswith(NOTE_PREFIX):
            if pending is None:
                raise AllowlistError(
                    f"{where}: note {line!r} has no entry to attach to. A "
                    f"'# ^ ...' note must sit on the line directly below the "
                    f"entry it annotates; use a plain '# ...' comment otherwise."
                )
            pending[2].append(line)
            continue
        close(pending)
        pending = None
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = sections.setdefault(name, Section(name=name))
            continue
        if current is None:
            _reject_inline_comment(line, where)
            entries.append(line)
            pending = (where, line, notes.setdefault(line, []))
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            current.kv[key.strip()] = value.strip()
            continue
        if current.name not in FREE_LINE_SECTIONS:
            raise AllowlistError(
                f"{where}: {line!r} under [{current.name}] is not a 'key=value' "
                f"line. Only [tsc-files] takes bare lines; entries such as "
                f"pytest/vitest ids belong above the first [section] header, not "
                f"under one (under one they allowlist nothing)."
            )
        _reject_inline_comment(line, where)
        current.lines.append(line)
        pending = (where, line, current.notes.setdefault(line, []))
    close(pending)
    return Allowlist(entries=entries, sections=sections, notes=notes)


def rel_to_repo(path: Path) -> str:
    """Repo-relative path for messages, falling back to the absolute path.

    ``Path.relative_to`` raises for anything outside the repo (a temporary
    allowlist in a test, a checkout symlinked elsewhere); a gate script must
    not die while composing its own error message.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def render_entries(entries, notes: dict) -> list[str]:
    """Render entries in order, each followed by its ``# ^`` note lines.

    ``--generate`` rewrites the whole file from a fresh measurement, so
    without this every note would be erased on the next regeneration. Notes
    for entries that are no longer in ``entries`` are simply not rendered:
    the note dies with the id it annotated.
    """
    out: list[str] = []
    for entry in entries:
        out.append(entry)
        out.extend(notes.get(entry, []))
    return out


def utc_today() -> str:
    """Today's date in UTC as ``YYYY-MM-DD``.

    UTC, not local time, so two maintainers in different time zones stamp the
    same regeneration with the same date.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def todo_note() -> str:
    """The placeholder note ``--generate`` writes under a brand-new id."""
    return TODO_NOTE_TEMPLATE.format(date=utc_today())


def fill_missing_notes(entries, notes: dict) -> dict:
    """Return ``notes`` with a TODO placeholder for every entry that has none.

    ``--generate`` measures ids the maintainer has never seen, so it cannot
    know their issue/stage note -- but the file it writes still has to parse,
    and the parser now requires a note per entry. Writing the placeholder
    makes the gap visible in the diff (and in the file) instead of producing
    a file that its own parser rejects.
    """
    filled = dict(notes)
    for entry in entries:
        if not filled.get(entry):
            filled[entry] = [todo_note()]
    return filled


# ---------------------------------------------------------------------------
# --generate guards
# ---------------------------------------------------------------------------
#
# --generate rewrites a baseline: the one line in the repo that says what is
# allowed to be broken. Two things must therefore be true of every run of it.
#
# 1. It says why. `regenerated=<date> <reason>` is written into the section it
#    rewrote, so a baseline that moved carries the reason for the move in the
#    file itself, not only in a commit message that the next reader has to go
#    and find. Exactly one such line is kept (the newest); git history holds
#    the earlier ones.
# 2. It cannot assert a version it did not measure. `--override-version`
#    exists to simulate a mismatched tool for the gate's own tests; combined
#    with --generate it would stamp a version= that nothing measured, which is
#    precisely the silent baseline corruption the version scheme exists to
#    prevent. So under --generate the override must equal the installed tool.

REGENERATED_KEY = "regenerated"

# Exit code for a --generate invoked without --reason: a usage error, like
# argparse's own, and distinct from 1 (the gate failed / refused).
USAGE_EXIT = 2


def regenerated_value(reason: str) -> str:
    """The value for the ``regenerated=`` key: UTC date, then the reason."""
    return f"{utc_today()} {' '.join(reason.split())}"


def was_now_line(metric: str, was_version, was_value, now_version, now_value) -> str:
    """One line naming what --generate changed, e.g.::

        was: version=0.8.6 baseline=200 -> now: version=0.8.6 baseline=190

    Printed before the write so the operator sees the delta they are about to
    commit -- a baseline that moves by 40 and one that moves by 1 look
    identical in the tool's exit code.
    """
    was_version = "none" if was_version is None else was_version
    was_value = "none" if was_value is None else was_value
    return (
        f"was: version={was_version} {metric}={was_value} -> "
        f"now: version={now_version} {metric}={now_value}"
    )


def check_generate_args(
    reason: "str | None",
    override_version: "str | None",
    tool_name: str,
    installed_version: "Callable[[], str]",
) -> "tuple[str, int] | None":
    """Validate a ``--generate`` request; return ``(message, exit_code)``.

    Returns ``None`` when the request is allowed to proceed.
    """
    if reason is None or not reason.strip():
        return (
            f'{tool_name}: --generate requires --reason "<text>" -- the reason is '
            f"written into the file as `{REGENERATED_KEY}=<date> <reason>`, so a "
            f"moved baseline says why it moved. Example: --generate --reason "
            f'"ruff 0.9.0 bump, 12 new RUF rules".',
            USAGE_EXIT,
        )
    if override_version:
        installed = installed_version()
        if installed != override_version:
            return (
                f"override-version {override_version} does not match the installed "
                f"{tool_name} {installed} -- a baseline may only carry the version "
                f"that measured it",
                1,
            )
    return None


# ---------------------------------------------------------------------------
# Tool version detection
# ---------------------------------------------------------------------------
#
# A baseline count (ruff findings, tsc errors) or a fixed set of node ids
# (pytest/vitest) is only meaningful relative to the tool version it was
# measured with. A dependency bump that makes a tool stricter (more rules
# enabled, new diagnostics) can inflate a count or introduce ids with no
# code change at all, which would either false-fail an unrelated PR or
# (worse) silently widen the allowlist. So every allowlist section also
# records the `version=` it was measured against, and the gate scripts
# below compare it to the tool version actually running before trusting
# the recorded baseline/ids.

_VERSION_RE = re.compile(r"\d+(?:\.\d+){1,3}(?:[a-zA-Z0-9.+-]*)?")


def _extract_version(text: str, tool_name: str) -> str:
    match = _VERSION_RE.search(text)
    if not match:
        raise RuntimeError(f"could not parse a {tool_name} version number from: {text!r}")
    return match.group(0)


def _tool_version(cmd: Sequence[str], tool_name: str) -> str:
    proc = run_cmd(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return _extract_version((proc.stdout or "") + (proc.stderr or ""), tool_name)


def get_ruff_version() -> str:
    """Return the running ``ruff`` version, e.g. ``"0.8.6"``."""
    return _tool_version(["uv", "run", "--no-sync", "ruff", "--version"], "ruff")


def get_tsc_version() -> str:
    """Return the running ``tsc`` (TypeScript compiler) version, e.g. ``"5.9.3"``."""
    return _tool_version(["npx", "tsc", "--version"], "tsc")


def get_vitest_version() -> str:
    """Return the running ``vitest`` version, e.g. ``"2.1.9"``."""
    return _tool_version(["npx", "vitest", "--version"], "vitest")


def get_pytest_version() -> str:
    """Return the running ``pytest`` version, e.g. ``"8.4.2"``."""
    return _tool_version(["uv", "run", "--no-sync", "pytest", "--version"], "pytest")


def get_python_version() -> str:
    """Return the running Python interpreter version, e.g. ``"3.12.10"``."""
    return _tool_version([sys.executable, "--version"], "python")


def render_other_sections(sections: dict, skip: set[str]) -> list[str]:
    """Render every section in ``sections`` except those named in ``skip``,
    in their original relative order, as ``[name]`` blocks.

    Each gate script's ``--generate`` mode rewrites the whole
    known_failures.txt file, but only knows about its own tool's section
    (``[ruff]``, ``[tsc-files]``, ``[pytest]`` or ``[vitest]``). Without
    this, regenerating e.g. just the ``[ruff]`` section after a ruff-only
    version bump would silently drop the ``[pytest]`` section (and its
    recorded ``version=``) that lives in the same file -- exactly the kind
    of silent baseline corruption this versioning scheme exists to prevent.
    So every write_* helper below calls this to carry forward whatever
    other sections were already on disk, unchanged -- including each one's
    ``regenerated=`` line, which belongs to the section it annotates and must
    not be reassigned to whichever tool happened to run last.
    """
    out: list[str] = []
    for name, section in sections.items():
        if name in skip:
            continue
        out.append("")
        out.append(f"[{name}]")
        for key, value in section.kv.items():
            out.append(f"{key}={value}")
        out.extend(render_entries(section.lines, section.notes))
    return out


def check_tool_version(
    section: "Section | None",
    running_version: str,
    tool_name: str,
    allowlist_rel: str,
) -> str | None:
    """Compare a recorded ``version=`` against the currently running tool.

    Returns ``None`` when they match, meaning the caller's normal
    count/allowlist comparison is trustworthy and should proceed as before.

    Returns a ready-to-print error message when they don't -- including
    when the section is missing a ``version=`` entirely (an allowlist file
    written before this check existed). In that case the caller must fail
    outright rather than compare counts or ids across tool versions, since
    a baseline measured under one tool version says nothing about another.
    """
    recorded = section.kv.get("version") if section else None
    if not recorded:
        return (
            f"{tool_name}: {allowlist_rel} has no recorded baseline tool version "
            f"(old-format allowlist without version=) -- re-measure with "
            f"{tool_name} {running_version} and update {allowlist_rel} in the "
            f"same commit as the bump."
        )
    if recorded != running_version:
        return (
            f"{tool_name} {running_version} is not the baseline tool version "
            f"{recorded} -- re-measure and update {allowlist_rel} in the same "
            f"commit as the bump"
        )
    return None
