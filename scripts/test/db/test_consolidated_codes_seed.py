"""
Guards the seed of `consolidated_codes` against silent drift.

init.sql and the live database are populated by two different paths, and they had
already diverged: init.sql carried '51-ФЗ' copied into GK_RF_2/3/4 (part one's act),
while the live rows carried NULL for the same columns. Nothing noticed.

This module parses the `INSERT INTO consolidated_codes ... VALUES` statement out of
docker/postgres/init.sql and compares the founding-act columns with the live rows.
Parsing-only checks always run; the comparison skips cleanly when no database is
reachable (CI without Docker).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

INIT_SQL = Path(__file__).resolve().parents[3] / "docker" / "postgres" / "init.sql"

# Columns compared between init.sql and the live DB.
COMPARED = (
    "original_eo_number",
    "original_date",
    "official_url",
    "founding_act_status",
)

EXPECTED_CODE_COUNT = 23


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
        eo = row.get("founding_act_eo_number")
        if eo is not None:
            assert re.fullmatch(r"\d{16}", eo), f"{code}: {eo!r} is not a portal eoNumber"


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

    query = text(
        "SELECT code, original_eo_number, original_date, official_url, founding_act_status "
        "FROM consolidated_codes"
    )
    try:
        with get_db_connection() as conn:
            result = conn.execute(query).mappings().all()
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    return {
        row["code"]: {
            "original_eo_number": row["original_eo_number"],
            "original_date": row["original_date"].isoformat() if row["original_date"] else None,
            "official_url": row["official_url"],
            "founding_act_status": row["founding_act_status"],
        }
        for row in result
    }


def test_live_db_has_the_same_codes_as_init_sql(seed, live_rows):
    assert set(live_rows) == set(seed), (
        f"only in DB: {sorted(set(live_rows) - set(seed))}; "
        f"only in init.sql: {sorted(set(seed) - set(live_rows))}"
    )


def test_live_db_founding_acts_match_init_sql(seed, live_rows):
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
