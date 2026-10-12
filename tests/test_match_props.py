from datetime import timedelta

import polars as pl
import pytest

from prop_engine import db
from prop_engine.config import Settings
from prop_engine.devig import convert_p_over, devig
from prop_engine.ingest_odds import SNAPSHOT_SCHEMA, normalize_event_odds
from prop_engine.match_props import match_run
from prop_engine.report import render


@pytest.fixture
def con_with_run(tmp_path, event_odds, captured):
    con = db.connect(tmp_path / "t.duckdb")
    df = pl.DataFrame(normalize_event_odds(event_odds, "r1", captured), schema=SNAPSHOT_SCHEMA)
    con.register("d", df.to_arrow())
    con.execute("INSERT INTO prop_snapshots SELECT * FROM d")
    con.execute("INSERT INTO runs VALUES ('r1', ?, 1, ?, 9, 100)", [captured, df.height])
    return con


def _by_player(matched):
    return {r["player_key"]: r for r in matched.iter_rows(named=True)}


def test_same_line_strong_under_qualifies(con_with_run, captured):
    m = _by_player(match_run(con_with_run, "r1", Settings(), now=captured + timedelta(minutes=5)))
    cook = m["james cook"]
    expected = (devig(2.25, 1.65).p_under + devig(2.20, 1.68).p_under) / 2
    assert cook["p_under"] == pytest.approx(expected)
    assert cook["n_sharp"] == 2
    assert cook["converted"] is False
    assert cook["qualifies"] == "lower"
    # FanDuel at 69.5 is converted to 70.5 for the consensus check only.
    assert cook["consensus_over"] is not None
    assert "fanduel" not in cook["books_used"]


def test_converted_line(con_with_run, captured):
    m = _by_player(match_run(con_with_run, "r1", Settings(), now=captured))
    kelce = m["travis kelce"]
    assert kelce["converted"] is True
    assert kelce["sharp_lines"] == "betonlineag:64.5,pinnacle:64.5"
    nv = devig(1.87, 1.95)
    pin_over = min(convert_p_over("player_reception_yds", p, 64.5, 66.5) for p in (nv.p_over_mult, nv.p_over_power))
    assert kelce["p_over"] < nv.p_over  # higher UD line -> lower P(higher)
    assert kelce["p_over"] < pin_over + 0.01
    assert kelce["qualifies"] is None


def test_rejects(con_with_run, captured):
    m = _by_player(match_run(con_with_run, "r1", Settings(), now=captured))
    # Pinnacle prices Allen; BetOnline's one-sided quote is ignored.
    assert m["josh allen"]["books_used"] == "pinnacle"
    assert m["josh allen"]["qualifies"] is None
    assert m["khalil shakir"]["reject_reason"] == "no sharp price"


def test_stale_snapshot_rejected(con_with_run, captured):
    matched = match_run(con_with_run, "r1", Settings(), now=captured + timedelta(minutes=20))
    assert matched["reject_reason"].str.starts_with("snapshot").all()


def test_game_started_rejected(con_with_run, captured):
    matched = match_run(con_with_run, "r1", Settings(max_staleness_min=1e9), now=captured + timedelta(days=4))
    assert (matched["reject_reason"] == "game started").all()


def test_rematch_is_idempotent_and_writes_no_vig(con_with_run, captured):
    for _ in range(2):
        match_run(con_with_run, "r1", Settings(), now=captured)
    assert con_with_run.execute("SELECT count(*) FROM matched_props").fetchone()[0] == 4
    methods = con_with_run.execute("SELECT DISTINCT method FROM no_vig ORDER BY 1").fetchall()
    assert methods == [("multiplicative",), ("power",)]
    books = {b for (b,) in con_with_run.execute("SELECT DISTINCT book FROM no_vig").fetchall()}
    assert "underdog" not in books


def test_report_renders(con_with_run, captured):
    matched = match_run(con_with_run, "r1", Settings(), now=captured)
    text = render(matched, "r1", captured, Settings())
    assert "James Cook" in text and "**LOWER**" in text
    assert "Rejected (no sharp price): 1" in text
    assert "| 5-pick | 20x | 54.9% |" in text


def test_report_pass_when_nothing_qualifies(con_with_run, captured):
    matched = match_run(con_with_run, "r1", Settings(leg_margin=0.5), now=captured)
    assert "**PASS**" in render(matched, "r1", captured, Settings())
