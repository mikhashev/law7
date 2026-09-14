"""Shared helpers for the CI gate scripts in this directory.

Kept dependency-free (stdlib only) so these scripts can run with either
``uv run --no-sync python ...`` (Python job) or a plain system ``python``
(Node job, which does not sync the project's Python environment).
"""

from __future__ import annotations

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
