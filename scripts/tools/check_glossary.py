"""Checker for docs/GLOSSARY.md against the rules it declares in its own section 5.

The glossary is a table of terms whose ``Defined by`` column must point at an
authority (an act, a standard, or -- for our own words -- a document in this
repository). This script enforces the shape rules described in the
glossary's section 5 ("How this file is checked") mechanically:

  1. every ``Defined by`` cell in sections 1-3 must resolve to a link, an act
     citation, a standard citation, or the literal ``citation unresolved``;
     a standard citation's URL must additionally resolve to a host on that
     standard's allowlist (``STANDARD_URL_HOSTS``, below);
  2. section 1 (law) rows specifically must cite an act or say ``citation
     unresolved`` -- a repository link alone does not count. An act citation
     of a state-authority type (Federal Law, Federal Constitutional Law,
     Presidential Decree, Government Decree) must give type + date + number
     + a quoted title, once per distinct act number cited in the cell;
     Constitution and Code citations need only an article reference, title
     optional. The accepted date form is ``DD.MM.YYYY``; ISO ``YYYY-MM-DD``
     is also accepted;
  3. the ``Meaning`` column must not carry a digit describing *our own*
     coverage: an integer of any size immediately followed (within two
     tokens) by a count noun (documents, codes, articles, tools, ... --
     see ``COUNT_NOUNS``), an "N of M" coverage fraction, or a percentage.
     Bare integers >= 1000 outside a citation span (a date, an act/article
     number, a version, a cited year, an arXiv id) are flagged too, even
     with no count noun nearby;
  4. every relative markdown link in the file must resolve to an existing
     file (and heading anchor, if one is given).

It does not fetch anything over the network: official URLs are checked for
shape only, never for liveness (see the glossary's own note on this).

Usage:
    uv run python scripts/tools/check_glossary.py [path] [--base-dir DIR] [--verbose]

Exit status is 1 if any violation was found, 0 otherwise. Violations are
printed one per line as ``file:line: message``.
"""

from __future__ import annotations

import argparse
import functools
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# GitHub heading slugs
# ---------------------------------------------------------------------------

_LEADING_HASHES_RE = re.compile(r"^\s*#{1,6}\s*")
_INLINE_MARKUP_RE = re.compile(r"[`*_]+")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SLUG_STRIP_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_SPACE_RE = re.compile(r"\s+")


def github_slug(heading_text: str) -> str:
    """Reproduce the GitHub heading-to-anchor rule used by section 5 of the glossary:
    lowercase, strip punctuation except hyphens, spaces to hyphens.

    Accepts either the bare heading text or a full ``## Heading`` line.
    """
    text = _LEADING_HASHES_RE.sub("", heading_text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _INLINE_MARKUP_RE.sub("", text)
    text = text.strip().lower()
    text = _SLUG_STRIP_RE.sub("", text)
    text = _SLUG_SPACE_RE.sub("-", text.strip())
    return text


_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@functools.lru_cache(maxsize=None)
def collect_heading_slugs(path: Path) -> frozenset:
    """Return the set of anchor slugs GitHub would generate for every
    heading in ``path``, including the ``-1``, ``-2``, ... suffixes it
    appends to duplicate slugs.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    counts: dict[str, int] = {}
    slugs = set()
    for line in text.splitlines():
        m = _HEADING_LINE_RE.match(line)
        if not m:
            continue
        base = github_slug(m.group(2))
        n = counts.get(base, 0)
        slug = base if n == 0 else f"{base}-{n}"
        counts[base] = n + 1
        slugs.add(slug)
    return frozenset(slugs)


# ---------------------------------------------------------------------------
# Markdown link handling
# ---------------------------------------------------------------------------

# A markdown link, excluding images (``![...]``).
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def is_external_link(url: str) -> bool:
    return bool(_SCHEME_RE.match(url)) or url.startswith("mailto:")


def resolve_link(url: str, base_dir: Path, self_path: Path) -> tuple[bool, str]:
    """Check whether a markdown link target resolves.

    Relative paths are resolved against ``base_dir``; a bare ``#anchor``
    link is resolved against ``self_path`` (the glossary file itself).
    External (http/https/mailto) links are never fetched -- only their
    presence is accepted here (liveness is explicitly out of scope, see
    the glossary's section 5).
    """
    if is_external_link(url):
        return True, "external link (not fetched)"

    path_part, has_anchor, anchor = url.partition("#")

    if path_part in ("", "."):
        target = self_path
    else:
        target = (base_dir / path_part).resolve()

    if not target.exists() or not target.is_file():
        return False, f"target file not found: {target}"

    if has_anchor and anchor:
        slugs = collect_heading_slugs(target)
        if anchor not in slugs:
            return False, f"anchor '#{anchor}' not found in {target}"

    return True, "ok"


def find_links(lines: list[str]):
    """Yield (line_no, link_text, url) for every markdown link in ``lines``."""
    for i, line in enumerate(lines, start=1):
        for m in LINK_RE.finditer(line):
            yield i, m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

SECTION_HEADING_RE = re.compile(r"^##\s+([1-4])\.\s")
_TABLE_LINE_RE = re.compile(r"^\s*\|(.*)\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")


def find_sections(lines: list[str]) -> dict[int, tuple[int, int]]:
    """Return {section_number: (start_index, end_index)} (0-based, end
    exclusive) for the top-level ``## N.`` sections in the file."""
    starts: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        m = SECTION_HEADING_RE.match(line)
        if m:
            starts.append((int(m.group(1)), i))
    sections: dict[int, tuple[int, int]] = {}
    for idx, (num, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines)
        sections[num] = (start, end)
    return sections


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    parts = re.split(r"(?<!\\)\|", inner)
    return [p.strip() for p in parts]


def parse_table(lines: list[str], start: int, end: int):
    """Find the first GFM table inside ``lines[start:end]``.

    Returns (header_cells, rows) where rows is a list of
    (line_no_1_based, cells).
    """
    i = start
    while i < end:
        line = lines[i]
        if _TABLE_LINE_RE.match(line) and i + 1 < end and _SEPARATOR_RE.match(lines[i + 1]):
            header = _split_row(line)
            rows = []
            j = i + 2
            while j < end and _TABLE_LINE_RE.match(lines[j]):
                rows.append((j + 1, _split_row(lines[j])))
                j += 1
            return header, rows
        i += 1
    return [], []


# ---------------------------------------------------------------------------
# "Defined by" form matching
# ---------------------------------------------------------------------------

STANDARD_NAMES = [
    "ELI",
    "ECLI",
    "Akoma Ntoso",
    "LegalDocML",
    "FRBR",
    "TUF",
    "TAF",
    "Sigstore",
    "Rekor",
    "Trillian",
    "USLM",
    "CLML",
]

# Per-standard allowlist of expected URL hosts (form (d)). Each entry is
# either a bare host ("ifla.org") or "host/path-prefix"
# ("github.com/sigstore") when the host alone is shared by unrelated
# projects. Data, not code: add a standard by adding a key here. A standard
# name that appears in STANDARD_NAMES but has no entry here is itself a
# violation (see find_standard_host_violations).
STANDARD_URL_HOSTS: dict[str, list[str]] = {
    "ELI": ["data.europa.eu", "op.europa.eu", "eur-lex.europa.eu"],
    "ECLI": ["e-justice.europa.eu", "eur-lex.europa.eu"],
    "Akoma Ntoso": ["docs.oasis-open.org", "oasis-open.org", "akomantoso.org"],
    "LegalDocML": ["docs.oasis-open.org", "oasis-open.org", "akomantoso.org"],
    "FRBR": ["ifla.org"],
    "TUF": [
        "theupdateframework.github.io",
        "theupdateframework.io",
        "github.com/openlawlibrary",
    ],
    "TAF": [
        "theupdateframework.github.io",
        "theupdateframework.io",
        "github.com/openlawlibrary",
    ],
    "Sigstore": [
        "docs.sigstore.dev",
        "sigstore.dev",
        "github.com/sigstore",
        "transparency.dev",
    ],
    "Rekor": [
        "docs.sigstore.dev",
        "sigstore.dev",
        "github.com/sigstore",
        "transparency.dev",
    ],
    "Trillian": [
        "docs.sigstore.dev",
        "sigstore.dev",
        "github.com/sigstore",
        "transparency.dev",
    ],
    "USLM": ["github.com/usgpo", "xml.house.gov"],
    "CLML": ["legislation.gov.uk", "github.com/legislation"],
}

ACT_TYPES_FULL = [
    "Federal Constitutional Law",
    "Federal Law",
    "Presidential Decree",
    "Government Decree",
]

# The accepted date forms in a citation: DD.MM.YYYY, and ISO YYYY-MM-DD as an
# accepted alternative.
_DATE_DMY_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
_DATE_YMD_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_DATE_ANY_RE = re.compile(rf"(?:{_DATE_DMY_RE.pattern})|(?:{_DATE_YMD_RE.pattern})")
_NUMBER_RE = re.compile(r"\bNo\.\s*[A-Za-z0-9\-]+")
_ART_RE = re.compile(r"\bart\.\s*\d+")
_CONST_RE = re.compile(r"\bConstitution of the Russian Federation\b")
_CODE_RE = re.compile(
    r"\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\s+Code(?:\s+of\s+the\s+Russian\s+Federation)?\b"
)
_TITLE_RE = re.compile(r"\xab([^\xbb]*)\xbb|\"([^\"]*)\"|“([^”]*)”")
_URL_RE = re.compile(r"https?://[^\s)]+")


def segment_matches_act_citation(segment: str) -> bool:
    """Form (b): type + date + number, or Constitution/Code + art. N."""
    has_full_type = any(t in segment for t in ACT_TYPES_FULL)
    has_date = bool(_DATE_ANY_RE.search(segment))
    has_number = bool(_NUMBER_RE.search(segment))
    if has_full_type and has_date and has_number:
        return True

    has_const = bool(_CONST_RE.search(segment))
    has_code = bool(_CODE_RE.search(segment))
    has_art = bool(_ART_RE.search(segment))
    return (has_const or has_code) and has_art


def _segment_title(segment: str) -> str | None:
    """Return the first non-empty quoted title («…», "…" or “…”) in
    ``segment``, or None if it has none (empty markers don't count)."""
    for m in _TITLE_RE.finditer(segment):
        content = next((g for g in m.groups() if g is not None), None)
        if content is not None and content.strip() != "":
            return content.strip()
    return None


def segment_has_empty_title(segment: str) -> bool:
    for m in _TITLE_RE.finditer(segment):
        content = next((g for g in m.groups() if g is not None), None)
        if content is not None and content.strip() == "":
            return True
    return False


def find_missing_act_titles(cell: str) -> list[str]:
    """Form (b), title requirement: a state-authority act citation (Federal
    Law / Federal Constitutional Law / Presidential Decree / Government
    Decree -- i.e. type + date + number) must be followed, somewhere in the
    cell, by a non-empty quoted title -- at least once per distinct act
    number the cell cites. The Constitution and Codes are exempt (article
    reference is enough, title optional).

    Returns the act-number strings (e.g. ``No. 5-FZ``) that have no title
    anywhere in the cell.
    """
    segments = [s.strip() for s in cell.split(";") if s.strip()] or [cell.strip()]
    has_title_by_number: dict[str, bool] = {}
    order: list[str] = []
    for seg in segments:
        has_full_type = any(t in seg for t in ACT_TYPES_FULL)
        has_date = bool(_DATE_ANY_RE.search(seg))
        num_match = _NUMBER_RE.search(seg)
        if not (has_full_type and has_date and num_match):
            continue
        number = num_match.group(0)
        titled = _segment_title(seg) is not None
        if number not in has_title_by_number:
            has_title_by_number[number] = titled
            order.append(number)
        else:
            has_title_by_number[number] = has_title_by_number[number] or titled
    return [number for number in order if not has_title_by_number[number]]


def has_citation_unresolved(cell: str) -> bool:
    """Form (c): the literal text 'citation unresolved', markdown emphasis
    markers and surrounding commentary aside."""
    stripped = re.sub(r"[*_`]", "", cell)
    return "citation unresolved" in stripped.lower()


def cell_matches_standard_citation(cell: str) -> bool:
    """Form (d): a known standard name plus an http(s) URL to its spec,
    anywhere in the cell (not fetched -- only checked for shape)."""
    if not any(re.search(r"\b" + re.escape(name) + r"\b", cell) for name in STANDARD_NAMES):
        return False
    m = _URL_RE.search(cell)
    if not m:
        return False
    parsed = urlparse(m.group(0))
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _url_host_allowed(url: str, allowlist: list[str]) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lstrip("/")
    for entry in allowlist:
        entry_host, _, entry_prefix = entry.partition("/")
        if host != entry_host:
            continue
        if not entry_prefix or path.startswith(entry_prefix):
            return True
    return False


def find_standard_host_violations(cell: str) -> list[str]:
    """Form (d), address requirement: the URL cited for a known standard
    must resolve to a host on that standard's allowlist
    (``STANDARD_URL_HOSTS``) -- citing the right standard's name next to
    the wrong organization's URL is still a violation."""
    problems: list[str] = []
    for name in STANDARD_NAMES:
        if not re.search(r"\b" + re.escape(name) + r"\b", cell):
            continue
        for m in _URL_RE.finditer(cell):
            url = m.group(0)
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            allowlist = STANDARD_URL_HOSTS.get(name)
            if allowlist is None:
                problems.append(
                    f"standard '{name}' has no entry in STANDARD_URL_HOSTS -- "
                    "add its expected hosts to the allowlist at the top of "
                    "check_glossary.py"
                )
                continue
            if not _url_host_allowed(url, allowlist):
                problems.append(
                    f"URL host {parsed.netloc} is not a known home of standard "
                    f"{name} (expected one of: {', '.join(allowlist)})"
                )
    return problems


@dataclass
class RowCheck:
    forms: set = field(default_factory=set)
    empty_title: bool = False
    missing_titles: list = field(default_factory=list)
    standard_host_problems: list = field(default_factory=list)


def evaluate_defined_by(cell: str, base_dir: Path, self_path: Path) -> RowCheck:
    result = RowCheck()

    segments = [s.strip() for s in cell.split(";") if s.strip()] or [cell.strip()]
    for seg in segments:
        if segment_matches_act_citation(seg):
            result.forms.add("b")
            if segment_has_empty_title(seg):
                result.empty_title = True

    result.missing_titles = find_missing_act_titles(cell)

    if has_citation_unresolved(cell):
        result.forms.add("c")

    if cell_matches_standard_citation(cell):
        result.forms.add("d")
    result.standard_host_problems = find_standard_host_violations(cell)

    for _line, _text, url in find_links([cell]):
        ok, _reason = resolve_link(url, base_dir, self_path)
        if ok:
            result.forms.add("a")

    return result


# ---------------------------------------------------------------------------
# Numbers rule (Meaning column) -- frame of reference, not magnitude
# ---------------------------------------------------------------------------
#
# Section 1 of the glossary forbids numbers that describe *our own* coverage
# (counts of documents, codes, articles, ...) because those drift and
# SCOPE.md is their one home. It does not forbid citing someone else's
# object -- a date, an act or article number, a standard's version, a
# paper's year. So the rule keys off what the digit is a count *of*, not how
# big it is.

# Count nouns whose adjacent integer names OUR coverage. Singular/plural,
# matched case-insensitively. Configurable: add a noun here to start
# catching it.
COUNT_NOUNS: dict[str, str] = {
    "document": "documents",
    "code": "codes",
    "article": "articles",
    "tool": "tools",
    "vector": "vectors",
    "test": "tests",
    "row": "rows",
    "line": "lines",
    "file": "files",
    "table": "tables",
    "column": "columns",
    "country": "countries",
    "jurisdiction": "jurisdictions",
    "version": "versions",
    "amendment": "amendments",
    "decision": "decisions",
    "interpretation": "interpretations",
    "server": "servers",
    "repository": "repositories",
    "commit": "commits",
    "star": "stars",
    "fork": "forks",
    "hit": "hits",
}
_COUNT_NOUN_FORMS = {form.lower() for pair in COUNT_NOUNS.items() for form in pair}

_NUM_GROUPED_RE = re.compile(r"\b\d{1,3}(?:[,\s]\d{3})+\b")
_NUM_PLAIN_RE = re.compile(r"\b\d+\b")
_PERCENT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?%")
_N_OF_M_RE = re.compile(
    r"\b\d[\d,]*\s+of\s+(?:the\s+)?\d[\d,]*\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z]+")

# Citation spans a number may legitimately sit inside without being a count
# of ours: DD.MM.YYYY / YYYY-MM-DD dates (``_DATE_DMY_RE`` / ``_DATE_YMD_RE``,
# defined above), "No. ..." act numbers, "art. ..." article references
# (including "art. 54(1) and 54(2)" chains), "Part N", "v1.0"-style
# versions, "(YYYY)" years, a year adjacent to a standard's name, and arXiv
# ids.
_ARXIV_RE = re.compile(r"\b\d{4}\.\d{5}\b")
_ACT_NO_RE = re.compile(r"\bNo\.\s*[A-Za-z0-9\-]+", re.IGNORECASE)
_ART_CHAIN_RE = re.compile(
    r"\bart\.\s*\d+(?:\(\d+\))?(?:\s*(?:,|and)\s*\d+(?:\(\d+\))?)*",
    re.IGNORECASE,
)
_PART_N_RE = re.compile(r"\bPart\s+\d+\b", re.IGNORECASE)
_VERSION_RE = re.compile(r"\bv\d+(?:\.\d+)*\b", re.IGNORECASE)
_YEAR_PAREN_RE = re.compile(r"\(\d{4}\)")
_STANDARD_YEAR_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(n) for n in STANDARD_NAMES) + r")\b[^\d\n]{0,30}\d{4}\b"
)

_EXEMPT_SPAN_RES = (
    _DATE_DMY_RE,
    _DATE_YMD_RE,
    _ARXIV_RE,
    _ACT_NO_RE,
    _ART_CHAIN_RE,
    _PART_N_RE,
    _VERSION_RE,
    _YEAR_PAREN_RE,
    _STANDARD_YEAR_RE,
)


def _exempt_spans(meaning: str) -> list[tuple[int, int]]:
    spans = []
    for rx in _EXEMPT_SPAN_RES:
        spans.extend(m.span() for m in rx.finditer(meaning))
    return spans


def _next_tokens(text: str, start: int, count: int) -> list[str]:
    tokens = []
    for m in _WORD_RE.finditer(text, start):
        tokens.append(m.group(0))
        if len(tokens) >= count:
            break
    return tokens


def find_number_violations(meaning: str) -> list[str]:
    """Numbers rule: flag an integer of any size that names OUR coverage --
    followed within two tokens by a count noun (``COUNT_NOUNS``), or part of
    an "N of M" coverage fraction, or a percentage. A bare integer >= 1000
    with no count noun nearby is flagged too. Citation spans (dates, act and
    article numbers, versions, cited years, arXiv ids) are exempt
    throughout.
    """
    problems: list[str] = []
    exempt = _exempt_spans(meaning)

    def is_exempt(span: tuple[int, int]) -> bool:
        return any(span[0] >= e[0] and span[1] <= e[1] for e in exempt)

    for m in _PERCENT_RE.finditer(meaning):
        problems.append(f"percentage '{m.group(0)}' in Meaning column")

    for m in _N_OF_M_RE.finditer(meaning):
        span = m.span()
        if is_exempt(span):
            continue
        problems.append(f"'{m.group(0)}' is an \"N of M\" coverage fraction in Meaning column")

    grouped_spans = [m.span() for m in _NUM_GROUPED_RE.finditer(meaning)]

    seen_spans: set[tuple[int, int]] = set()
    for rx in (_NUM_GROUPED_RE, _NUM_PLAIN_RE):
        for m in rx.finditer(meaning):
            span = m.span()
            if rx is _NUM_PLAIN_RE and any(
                span[0] >= g[0] and span[1] <= g[1] for g in grouped_spans
            ):
                continue  # already covered as part of a grouped number
            if span in seen_spans:
                continue
            seen_spans.add(span)

            if is_exempt(span):
                continue

            tokens = _next_tokens(meaning, span[1], 2)
            noun = next((t for t in tokens if t.lower() in _COUNT_NOUN_FORMS), None)
            if noun is not None:
                problems.append(
                    f"number '{m.group(0)}' precedes count noun '{noun}' in Meaning "
                    "column (a count of our own coverage belongs in SCOPE.md, not here)"
                )
                continue

            value = int(m.group(0).replace(",", "").replace(" ", ""))
            if value >= 1000:
                problems.append(f"number '{m.group(0)}' (>= 1000) in Meaning column")

    return problems


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    line: int
    message: str


def check_glossary(path: Path, base_dir: Path) -> tuple[list[Violation], list[dict]]:
    """Run every rule in section 5 against ``path``.

    Returns (violations, verbose_rows) where verbose_rows describes, for
    every row in sections 1-3, which Defined-by forms matched (for --verbose).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[Violation] = []
    verbose_rows: list[dict] = []

    sections = find_sections(lines)

    for sec_num in (1, 2, 3):
        if sec_num not in sections:
            continue
        start, end = sections[sec_num]
        _header, rows = parse_table(lines, start, end)
        for line_no, cells in rows:
            if len(cells) < 3:
                violations.append(
                    Violation(line_no, f"malformed row in section {sec_num} (expected 3 columns)")
                )
                continue
            term, meaning, defined_by = cells[0], cells[1], cells[2]

            check = evaluate_defined_by(defined_by, base_dir, path)
            verbose_rows.append(
                {
                    "line": line_no,
                    "section": sec_num,
                    "term": term,
                    "forms": sorted(check.forms),
                }
            )

            if not check.forms:
                violations.append(
                    Violation(
                        line_no,
                        f"'{term}': Defined-by cell has no recognized citation "
                        "(need a resolving link, an act citation, a standard "
                        "citation, or 'citation unresolved')",
                    )
                )
            elif sec_num == 1 and not (check.forms & {"b", "c"}):
                violations.append(
                    Violation(
                        line_no,
                        f"'{term}': legal row cites the repo instead of an act "
                        "(a repository link alone does not satisfy section 1)",
                    )
                )

            if check.empty_title:
                violations.append(
                    Violation(
                        line_no,
                        f"'{term}': act citation has an empty title marker (\xab\xbb or “”)",
                    )
                )

            for number in check.missing_titles:
                violations.append(
                    Violation(
                        line_no,
                        f"'{term}': act citation '{number}' is missing its quoted title "
                        "(Federal Law / Federal Constitutional Law / Presidential Decree / "
                        "Government Decree citations require type + date + number + title)",
                    )
                )

            for problem in check.standard_host_problems:
                violations.append(Violation(line_no, f"'{term}': {problem}"))

            for problem in find_number_violations(meaning):
                violations.append(Violation(line_no, f"'{term}': {problem}"))

    # Rule 5: every relative markdown link anywhere in the file must resolve.
    for line_no, _text, url in find_links(lines):
        ok, reason = resolve_link(url, base_dir, path)
        if not ok:
            violations.append(Violation(line_no, f"broken link '{url}': {reason}"))

    violations.sort(key=lambda v: v.line)
    return violations, verbose_rows


def print_verbose(verbose_rows: list[dict]) -> None:
    print("Defined-by form matches (a=link, b=act citation, c=unresolved, d=standard):")
    width = max((len(r["term"]) for r in verbose_rows), default=4)
    for row in verbose_rows:
        forms = ",".join(row["forms"]) or "(none)"
        print(
            f"  line {row['line']:>5}  section {row['section']}  "
            f"{row['term']:<{width}}  forms: {forms}"
        )
    print()


def main(argv: list[str] | None = None) -> int:
    # Term cells routinely carry Cyrillic glosses; on a legacy Windows
    # console (cp1252) a plain print() of those would crash instead of
    # reporting violations. Degrade gracefully rather than raising.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        default="docs/GLOSSARY.md",
        type=Path,
        help="Glossary file to check (default: docs/GLOSSARY.md)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Directory relative links are resolved against (default: the glossary file's own directory)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print which Defined-by form matched each row"
    )
    args = parser.parse_args(argv)

    path = args.path.resolve()
    if not path.exists():
        print(f"{args.path}: file not found", file=sys.stderr)
        return 1

    base_dir = args.base_dir.resolve() if args.base_dir else path.parent

    violations, verbose_rows = check_glossary(path, base_dir)

    if args.verbose:
        print_verbose(verbose_rows)

    for v in violations:
        print(f"{path}:{v.line}: {v.message}")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
