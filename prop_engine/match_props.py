"""match_props: join each Underdog prop to the sharp books, devig, convert to
Underdog's line, and price both directions against the leg floor (SPEC §1, §3)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import duckdb
import polars as pl

from .config import Settings, UNDERDOG
from .devig import ConversionError, convert_p_over, devig

MATCHED_SCHEMA = {
    "run_id": pl.Utf8,
    "event_id": pl.Utf8,
    "commence_time": pl.Datetime("us", "UTC"),
    "matchup": pl.Utf8,
    "market": pl.Utf8,
    "player_name": pl.Utf8,
    "player_key": pl.Utf8,
    "ud_line": pl.Float64,
    "books_used": pl.Utf8,
    "n_sharp": pl.Int32,
    "sharp_lines": pl.Utf8,
    "converted": pl.Boolean,
    "p_over": pl.Float64,
    "p_under": pl.Float64,
    "consensus_over": pl.Float64,
    "edge_over": pl.Float64,
    "edge_under": pl.Float64,
    "qualifies": pl.Utf8,
    "reject_reason": pl.Utf8,
}

NO_VIG_SCHEMA = {
    "run_id": pl.Utf8,
    "event_id": pl.Utf8,
    "book": pl.Utf8,
    "market": pl.Utf8,
    "player_key": pl.Utf8,
    "line": pl.Float64,
    "method": pl.Utf8,
    "p_over": pl.Float64,
    "p_under": pl.Float64,
}


def _price_at_line(quotes: list[dict], market: str, ud_line: float) -> tuple[float, float, float] | str:
    """Use the book's quote closest to Underdog's line. Returns
    (p_over, p_under, sharp_line) at Underdog's line, both conservative, or an error."""
    usable = [q for q in quotes if q["line"] is not None and q["over_price"] and q["under_price"]]
    if not usable:
        return "one-sided or missing price"
    q = min(usable, key=lambda r: abs(r["line"] - ud_line))
    nv = devig(q["over_price"], q["under_price"])
    try:
        overs = [convert_p_over(market, p, q["line"], ud_line) for p in (nv.p_over_mult, nv.p_over_power)]
        unders = [
            1.0 - convert_p_over(market, 1.0 - p, q["line"], ud_line)
            for p in (nv.p_under_mult, nv.p_under_power)
        ]
    except ConversionError as exc:
        return str(exc)
    return min(overs), min(unders), q["line"]


def match_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    settings: Settings,
    now: datetime | None = None,
) -> pl.DataFrame:
    snap = con.execute("SELECT * FROM prop_snapshots WHERE run_id = ?", [run_id]).pl()
    now = now or datetime.now(timezone.utc)

    no_vig_rows = []
    for r in snap.filter(pl.col("over_price").is_not_null() & pl.col("under_price").is_not_null()).iter_rows(named=True):
        if r["book"] == UNDERDOG or r["line"] is None:
            continue
        nv = devig(r["over_price"], r["under_price"])
        for method, po, pu in (("multiplicative", nv.p_over_mult, nv.p_under_mult), ("power", nv.p_over_power, nv.p_under_power)):
            no_vig_rows.append({
                "run_id": run_id, "event_id": r["event_id"], "book": r["book"], "market": r["market"],
                "player_key": r["player_key"], "line": r["line"], "method": method, "p_over": po, "p_under": pu,
            })

    # (event, market, player) -> book -> quotes
    quotes: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in snap.iter_rows(named=True):
        quotes[(r["event_id"], r["market"], r["player_key"])][r["book"]].append(r)

    floor, margin = settings.leg_floor, settings.leg_margin
    out = []
    for (event_id, market, pkey), by_book in quotes.items():
        for ud in by_book.get(UNDERDOG, []):
            row = {
                "run_id": run_id,
                "event_id": event_id,
                "commence_time": ud["commence_time"],
                "matchup": f"{ud['away_team']} @ {ud['home_team']}",
                "market": market,
                "player_name": ud["player_name"],
                "player_key": pkey,
                "ud_line": ud["line"],
                "books_used": None, "n_sharp": 0, "sharp_lines": None, "converted": None,
                "p_over": None, "p_under": None, "consensus_over": None,
                "edge_over": None, "edge_under": None, "qualifies": None, "reject_reason": None,
            }
            out.append(row)

            age_min = (now - ud["captured_at"]).total_seconds() / 60
            if age_min > settings.max_staleness_min:
                row["reject_reason"] = f"snapshot {age_min:.0f} min old"
                continue
            if ud["line"] is None:
                row["reject_reason"] = "no Underdog line"
                continue
            if ud["commence_time"] is not None and ud["commence_time"] <= now:
                row["reject_reason"] = "game started"
                continue

            sharp, errors = {}, []
            for book in settings.sharp_books:
                if book in by_book:
                    res = _price_at_line(by_book[book], market, ud["line"])
                    if isinstance(res, str):
                        errors.append(f"{book}: {res}")
                    else:
                        sharp[book] = res
            if not sharp:
                row["reject_reason"] = "; ".join(errors) if errors else "no sharp price"
                continue

            consensus = [
                res[0] for book in settings.consensus_books if book in by_book
                for res in [_price_at_line(by_book[book], market, ud["line"])] if not isinstance(res, str)
            ]

            p_over = sum(v[0] for v in sharp.values()) / len(sharp)
            p_under = sum(v[1] for v in sharp.values()) / len(sharp)
            row.update({
                "books_used": ",".join(sorted(sharp)),
                "n_sharp": len(sharp),
                "sharp_lines": ",".join(f"{b}:{v[2]:g}" for b, v in sorted(sharp.items())),
                "converted": any(v[2] != ud["line"] for v in sharp.values()),
                "p_over": p_over,
                "p_under": p_under,
                "consensus_over": sum(consensus) / len(consensus) if consensus else None,
                "edge_over": p_over - floor,
                "edge_under": p_under - floor,
            })
            if p_over - floor >= margin:
                row["qualifies"] = "higher"
            elif p_under - floor >= margin:
                row["qualifies"] = "lower"

    matched = pl.DataFrame(out, schema=MATCHED_SCHEMA)
    no_vig = pl.DataFrame(no_vig_rows, schema=NO_VIG_SCHEMA)

    # Idempotent per run: re-matching replaces the previous output.
    con.execute("DELETE FROM matched_props WHERE run_id = ?", [run_id])
    con.execute("DELETE FROM no_vig WHERE run_id = ?", [run_id])
    for table, df in (("matched_props", matched), ("no_vig", no_vig)):
        con.register("tmp_df", df.to_arrow())
        con.execute(f"INSERT INTO {table} SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    return matched
