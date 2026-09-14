"""
Guards the seed of `consolidated_codes` against silent drift.

init.sql and the live database are populated by two different paths, and they had
already diverged: init.sql carried '51-ФЗ' copied into GK_RF_2/3/4 (part one's act),
while the live rows carried NULL for the same columns. Nothing noticed.

This module parses the `INSERT INTO consolidated_codes ... VALUES` statement out of
docker/postgres/init.sql and compares EVERY seeded column with the live rows - not
just the founding-act ones and not just the row count. The narrower comparison used
to pass while init.sql and the live DB disagreed on name/short_name/description for
eight rows. Parsing-only checks always run; the comparison skips cleanly when no
database is reachable (CI without Docker).

It also guards the referent rules settled in migration 004: official_url_kind must
describe the URL actually stored, the Constitution's 2020 official text must never
be filed as a founding act, and all 23 founding_act_title values must follow one
convention.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

INIT_SQL = Path(__file__).resolve().parents[3] / "docker" / "postgres" / "init.sql"

# Every seeded column is compared between init.sql and the live DB ('code' is the key).
COMPARED = (
    "name",
    "short_name",
    "description",
    "original_eo_number",
    "original_date",
    "official_url",
    "official_url_kind",
    "ips_document_type",
    "founding_act_title",
    "founding_act_eo_number",
    "official_text_eo_number",
    "founding_act_status",
    "founding_act_published_at",
)

# Columns the live query returns as dates and compares as ISO strings.
DATE_COLUMNS = ("original_date", "founding_act_published_at")

EXPECTED_CODE_COUNT = 23

# One title convention: "<act type> от DD.MM.YYYY № <number> «<official name>»".
TITLE_RE = re.compile(
    r"^Федеральный (?:конституционный )?закон от (\d{2}\.\d{2}\.\d{4}) № (\S+) «(.+)»$"
)

# The Constitution has no adopting act: it is titled by its own name alone.
CONSTITUTION_TITLE = "Конституция Российской Федерации"

# Portal id of the official text of the Constitution with the 2020 amendments.
# It is NOT a founding act; it belongs in official_text_eo_number.
KONST_OFFICIAL_TEXT_EO = "0001202007040001"

IPS_DOCUMENT_TYPES = {"Кодекс", "Конституция", "Федеральный закон"}


# ---------------------------------------------------------------------------
# Minimal SQL literal parsing
# ---------------------------------------------------------------------------


def _split_top_level(text: str) -> list[str]:
    """Split a VALUES body into row tuples, ignoring parens inside string literals."""
    rows: list[str] = []
    depth = 0
    in_str = False
    start = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":  # escaped quote
                    i += 2
                    continue
                in_str = False
        elif ch == "'":
            in_str = True
        elif ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                rows.append(text[start:i])
                start = None
        i += 1
    return rows


def _split_fields(row: str) -> list[str]:
    """Split one row tuple on top-level commas."""
    fields: list[str] = []
    buf: list[str] = []
    in_str = False
    i = 0
    while i < len(row):
        ch = row[i]
        if in_str:
            buf.append(ch)
            if ch == "'":
                if i + 1 < len(row) and row[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
        elif ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == ",":
            fields.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    fields.append("".join(buf).strip())
    return fields


def _literal(token: str):
    token = token.strip()
    if token.upper() == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    return token


def parse_init_sql_seed(sql_text: str) -> dict[str, dict]:
    """Return {code: {column: value}} for the consolidated_codes INSERT."""
    match = re.search(
        r"INSERT\s+INTO\s+consolidated_codes\s*\(([^)]*)\)\s*VALUES(.*?)ON\s+CONFLICT",
        sql_text,
        re.S | re.I,
    )
    assert match, "consolidated_codes INSERT not found in init.sql"

    columns = [c.strip() for c in match.group(1).split(",")]
    seed: dict[str, dict] = {}
    for row in _split_top_level(match.group(2)):
        values = [_literal(f) for f in _split_fields(row)]
        assert len(values) == len(columns), f"column/value mismatch in row: {row[:80]}"
        record = dict(zip(columns, values))
        seed[record["code"]] = record
    return seed


@pytest.fixture(scope="module")
def seed() -> dict[str, dict]:
    return parse_init_sql_seed(INIT_SQL.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Checks on init.sql alone (no database needed)
# ---------------------------------------------------------------------------


def test_seed_has_all_codes(seed):
    assert len(seed) == EXPECTED_CODE_COUNT


def test_every_seed_row_carries_the_founding_act_columns(seed):
    for code, row in seed.items():
        for column in COMPARED:
            assert column in row, f"{code}: init.sql INSERT is missing {column}"


def test_no_seed_row_is_left_unknown(seed):
    """'unknown' means nobody checked; every shipped row must be 'known' or 'none'."""
    unresolved = [c for c, r in seed.items() if r["founding_act_status"] not in ("known", "none")]
    assert not unresolved, f"founding act not established for: {unresolved}"


def test_only_the_constitution_has_no_act_number(seed):
    """NULL act number is legitimate only where status says 'none'."""
    for code, row in seed.items():
        if row["original_eo_number"] is None:
            assert row["founding_act_status"] == "none", f"{code}: NULL number but status is not 'none'"
        else:
            assert row["founding_act_status"] == "known", f"{code}: has a number but status is not 'known'"
    assert seed["KONST_RF"]["founding_act_status"] == "none"


def test_every_seed_row_has_an_official_url(seed):
    missing = [c for c, r in seed.items() if not r["official_url"]]
    assert not missing, f"official_url missing for: {missing}"


def test_parts_carry_their_own_founding_act(seed):
    """GK_RF_2/3/4 and NK_RF_2 used to copy part one's act. They must not again."""
    assert seed["GK_RF"]["original_eo_number"] == "51-ФЗ"
    assert seed["GK_RF_2"]["original_eo_number"] == "14-ФЗ"
    assert seed["GK_RF_3"]["original_eo_number"] == "146-ФЗ"
    assert seed["GK_RF_4"]["original_eo_number"] == "230-ФЗ"
    assert seed["NK_RF"]["original_eo_number"] == "146-ФЗ"
    assert seed["NK_RF_2"]["original_eo_number"] == "117-ФЗ"

    parts = ["GK_RF", "GK_RF_2", "GK_RF_3", "GK_RF_4", "NK_RF", "NK_RF_2"]
    acts = {(seed[c]["original_eo_number"], seed[c]["original_date"]) for c in parts}
    assert len(acts) == len(parts), "two parts share one founding act again"


def test_act_number_collision_is_expected_and_disambiguated_by_date(seed):
    """146-ФЗ is both NK_RF (1998) and GK_RF_3 (2001): never key on the number alone."""
    by_number: dict[str, list[str]] = {}
    for code, row in seed.items():
        if row["original_eo_number"]:
            by_number.setdefault(row["original_eo_number"], []).append(code)

    collisions = {n: sorted(c) for n, c in by_number.items() if len(c) > 1}
    assert collisions == {"146-ФЗ": ["GK_RF_3", "NK_RF"]}, f"unexpected collisions: {collisions}"

    # The (number, date) pair must still be unique across all rows.
    pairs = [
        (r["original_eo_number"], r["original_date"])
        for r in seed.values()
        if r["original_eo_number"]
    ]
    assert len(pairs) == len(set(pairs))


def test_portal_eo_numbers_look_like_portal_eo_numbers(seed):
    """A portal eoNumber is 16 digits; an act number like '51-ФЗ' is not one."""
    for code, row in seed.items():
        for column in ("founding_act_eo_number", "official_text_eo_number"):
            eo = row.get(column)
            if eo is not None:
                assert re.fullmatch(r"\d{16}", eo), f"{code}.{column}: {eo!r} is not an eoNumber"


# ---------------------------------------------------------------------------
# Referent rules (migration 004): which object does each column describe?
# ---------------------------------------------------------------------------


def test_official_url_kind_says_what_the_url_points_at(seed):
    """official_url holds two different kinds of object; the kind column must say which."""
    for code, row in seed.items():
        kind = row["official_url_kind"]
        url = row["official_url"]
        assert kind in ("act_publication", "code_record"), f"{code}: bad kind {kind!r}"
        if kind == "act_publication":
            assert "publication.pravo.gov.ru" in url, f"{code}: act_publication but URL is {url!r}"
            eo = row["founding_act_eo_number"]
            assert eo, f"{code}: act_publication without a founding-act eoNumber"
            assert eo in url, f"{code}: URL {url!r} does not carry eoNumber {eo!r}"
        else:
            assert "pravo.gov.ru/proxy/ips/" in url, f"{code}: code_record but URL is {url!r}"


def test_only_kas_rf_is_anchored_to_an_act_publication(seed):
    """No pre-2011 founding act has a portal artifact, so 22 rows anchor to the code record."""
    act_rows = sorted(c for c, r in seed.items() if r["official_url_kind"] == "act_publication")
    assert act_rows == ["KAS_RF"], f"unexpected act_publication rows: {act_rows}"
    assert seed["KAS_RF"]["founding_act_eo_number"] == "0001201503090041"


def test_the_constitution_separates_the_act_from_the_official_text(seed):
    """0001202007040001 is the 2020 official TEXT, never a founding act."""
    konst = seed["KONST_RF"]
    assert konst["founding_act_status"] == "none"
    assert konst["founding_act_eo_number"] is None, "the Constitution has no founding-act eoNumber"
    assert konst["official_text_eo_number"] == KONST_OFFICIAL_TEXT_EO
    assert konst["original_eo_number"] is None

    # Nobody else claims an official consolidated text.
    others = sorted(
        c for c, r in seed.items() if c != "KONST_RF" and r["official_text_eo_number"] is not None
    )
    assert not others, f"unexpected official_text_eo_number on: {others}"

    # 'none' must never coexist with a founding-act eoNumber anywhere.
    for code, row in seed.items():
        if row["founding_act_status"] == "none":
            assert row["founding_act_eo_number"] is None, f"{code}: status none, act eoNumber set"


def test_one_title_convention_for_every_row(seed):
    """Title = official designation of the ADOPTING ACT, identical convention in all rows."""
    for code, row in seed.items():
        title = row["founding_act_title"]
        if code == "KONST_RF":
            assert title == CONSTITUTION_TITLE, f"KONST_RF title is {title!r}"
            continue
        match = TITLE_RE.match(title)
        assert match, f"{code}: title does not follow the convention: {title!r}"
        date, number, name = match.groups()
        day, month, year = row["original_date"].split("-")[::-1]
        assert date == f"{day}.{month}.{year}", f"{code}: title date {date} != original_date"
        assert number == row["original_eo_number"], f"{code}: title number {number} != act number"
        assert name == row["name"], f"{code}: title name {name!r} != name {row['name']!r}"


def test_no_title_carries_the_ips_classification_as_the_act_type(seed):
    """«Кодекс Российской Федерации от ...» was the ИПС document type, not the act type."""
    offenders = [c for c, r in seed.items() if r["founding_act_title"].startswith("Кодекс ")]
    assert not offenders, f"ИПС classification used as act type in: {offenders}"


def test_ips_document_type_classifies_the_object_at_official_url(seed):
    for code, row in seed.items():
        ips_type = row["ips_document_type"]
        assert ips_type in IPS_DOCUMENT_TYPES, f"{code}: unexpected ips_document_type {ips_type!r}"
        if row["official_url_kind"] == "act_publication":
            assert ips_type == "Федеральный закон", f"{code}: act publication typed {ips_type!r}"
    assert seed["KONST_RF"]["ips_document_type"] == "Конституция"
    assert seed["GK_RF"]["ips_document_type"] == "Кодекс"


def test_short_name_is_a_display_label_and_not_a_key(seed):
    """«ВК РФ» belongs to two different codes: never look a code up by short_name."""
    by_short: dict[str, list[str]] = {}
    for code, row in seed.items():
        by_short.setdefault(row["short_name"], []).append(code)
    collisions = {s: sorted(c) for s, c in by_short.items() if len(c) > 1}
    assert collisions == {"ВК РФ": ["VDK_RF", "VZK_RF"]}, f"unexpected short_name map: {collisions}"


# ---------------------------------------------------------------------------
# init.sql vs. the live database
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_rows():
    """Rows from the running database, or skip when it is not reachable."""
    try:
        from sqlalchemy import text

        from scripts.core.db import get_db_connection
    except Exception as exc:  # pragma: no cover - import environment dependent
        pytest.skip(f"database client unavailable: {exc}")

    query = text("SELECT code, " + ", ".join(COMPARED) + " FROM consolidated_codes")
    try:
        with get_db_connection() as conn:
            result = conn.execute(query).mappings().all()
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    def value(row, column):
        raw = row[column]
        if column in DATE_COLUMNS:
            return raw.isoformat() if raw else None
        return raw

    return {row["code"]: {c: value(row, c) for c in COMPARED} for row in result}


def test_live_db_has_the_same_codes_as_init_sql(seed, live_rows):
    assert set(live_rows) == set(seed), (
        f"only in DB: {sorted(set(live_rows) - set(seed))}; "
        f"only in init.sql: {sorted(set(seed) - set(live_rows))}"
    )


def test_live_db_matches_init_sql_in_every_seeded_column(seed, live_rows):
    drift = []
    for code in sorted(seed):
        if code not in live_rows:
            continue
        for column in COMPARED:
            expected = seed[code][column]
            actual = live_rows[code][column]
            if expected != actual:
                drift.append(f"{code}.{column}: init.sql={expected!r} db={actual!r}")
    assert not drift, "init.sql and the live DB have drifted:\n" + "\n".join(drift)
