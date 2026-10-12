"""DuckDB storage. One file; every ingest run appends a timestamped snapshot so
as-of history accumulates from day one (SPEC §9: history can't be backfilled)."""

from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id            VARCHAR PRIMARY KEY,
    captured_at       TIMESTAMPTZ NOT NULL,
    n_events          INTEGER,
    n_rows            INTEGER,
    credits_used      INTEGER,
    credits_remaining INTEGER
);

-- SPEC PropSnapshot. event_id stands in for game_id and player_key (normalized
-- name) for player_id until week 3 maps both to nflverse ids.
CREATE TABLE IF NOT EXISTS prop_snapshots (
    run_id            VARCHAR NOT NULL,
    captured_at       TIMESTAMPTZ NOT NULL,
    event_id          VARCHAR NOT NULL,
    commence_time     TIMESTAMPTZ,
    home_team         VARCHAR,
    away_team         VARCHAR,
    book              VARCHAR NOT NULL,
    market            VARCHAR NOT NULL,
    player_name       VARCHAR NOT NULL,
    player_key        VARCHAR NOT NULL,
    line              DOUBLE,
    over_price        DOUBLE,
    under_price       DOUBLE,
    multiplier        DOUBLE,
    source_updated_at TIMESTAMPTZ
);

-- SPEC NoVig, one row per book/prop/method.
CREATE TABLE IF NOT EXISTS no_vig (
    run_id      VARCHAR NOT NULL,
    event_id    VARCHAR NOT NULL,
    book        VARCHAR NOT NULL,
    market      VARCHAR NOT NULL,
    player_key  VARCHAR NOT NULL,
    line        DOUBLE NOT NULL,
    method      VARCHAR NOT NULL,
    p_over      DOUBLE NOT NULL,
    p_under     DOUBLE NOT NULL
);

-- Output of match_props: one row per Underdog prop, both directions priced.
CREATE TABLE IF NOT EXISTS matched_props (
    run_id          VARCHAR NOT NULL,
    event_id        VARCHAR NOT NULL,
    commence_time   TIMESTAMPTZ,
    matchup         VARCHAR,
    market          VARCHAR NOT NULL,
    player_name     VARCHAR NOT NULL,
    player_key      VARCHAR NOT NULL,
    ud_line         DOUBLE,
    books_used      VARCHAR,
    n_sharp         INTEGER,
    sharp_lines     VARCHAR,
    converted       BOOLEAN,
    p_over          DOUBLE,
    p_under         DOUBLE,
    consensus_over  DOUBLE,
    edge_over       DOUBLE,
    edge_under      DOUBLE,
    qualifies       VARCHAR,
    reject_reason   VARCHAR
);
"""


def connect(path: Path | str) -> duckdb.DuckDBPyConnection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("SET TimeZone = 'UTC'")
    con.execute(SCHEMA)
    return con


def latest_run_id(con: duckdb.DuckDBPyConnection) -> str | None:
    row = con.execute("SELECT run_id FROM runs ORDER BY captured_at DESC LIMIT 1").fetchone()
    return row[0] if row else None
