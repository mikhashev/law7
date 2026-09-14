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
from pathlib import Path
from typing import Sequence

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


@dataclass
class Section:
    name: str
    kv: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)


@dataclass
class Allowlist:
    entries: list  # preamble plain entries, in file order, before any [section]
    sections: dict  # section name -> Section


def parse_allowlist(path: Path) -> Allowlist:
    """Parse a known_failures.txt file.

    Format:
        # comment (ignored)
        <plain entry>            # e.g. a pytest node id or vitest test name
        ...
        [section-name]
        key=value
        <plain entry within the section>   # e.g. a file path for [tsc-files]

    Entries before the first ``[section]`` header are returned in
    ``entries``; the file is UTF-8 and tolerant of CRLF or LF line endings
    (``str.splitlines`` handles both).
    """
    entries: list = []
    sections: dict = {}
    current: Section | None = None
    if not path.exists():
        return Allowlist(entries=entries, sections=sections)
    text = path.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = sections.setdefault(name, Section(name=name))
            continue
        if current is None:
            entries.append(line)
        elif "=" in line:
            key, _, value = line.partition("=")
            current.kv[key.strip()] = value.strip()
        else:
            current.lines.append(line)
    return Allowlist(entries=entries, sections=sections)


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
    other sections were already on disk, unchanged.
    """
    out: list[str] = []
    for name, section in sections.items():
        if name in skip:
            continue
        out.append("")
        out.append(f"[{name}]")
        for key, value in section.kv.items():
            out.append(f"{key}={value}")
        out.extend(section.lines)
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
