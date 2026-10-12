"""ingest_odds: pull sharp + Underdog player props and store a timestamped snapshot."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import duckdb
import polars as pl

from .config import Settings
from .names import player_key
from .odds_api import OddsApiClient

log = logging.getLogger(__name__)

SNAPSHOT_SCHEMA = {
    "run_id": pl.Utf8,
    "captured_at": pl.Datetime("us", "UTC"),
    "event_id": pl.Utf8,
    "commence_time": pl.Datetime("us", "UTC"),
    "home_team": pl.Utf8,
    "away_team": pl.Utf8,
    "book": pl.Utf8,
    "market": pl.Utf8,
    "player_name": pl.Utf8,
    "player_key": pl.Utf8,
    "line": pl.Float64,
    "over_price": pl.Float64,
    "under_price": pl.Float64,
    "multiplier": pl.Float64,
    "source_updated_at": pl.Datetime("us", "UTC"),
}


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_event_odds(event: dict, run_id: str, captured_at: datetime) -> list[dict]:
    """Flatten one /events/{id}/odds response into one row per book/market/player/line,
    with the Over and Under prices side by side."""
    rows: dict[tuple, dict] = {}
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            for oc in mkt.get("outcomes", []):
                side = (oc.get("name") or "").lower()
                name = oc.get("description")
                if side not in ("over", "under") or not name:
                    continue
                key = (bm["key"], mkt["key"], player_key(name), oc.get("point"))
                row = rows.setdefault(
                    key,
                    {
                        "run_id": run_id,
                        "captured_at": captured_at,
                        "event_id": event["id"],
                        "commence_time": _ts(event.get("commence_time")),
                        "home_team": event.get("home_team"),
                        "away_team": event.get("away_team"),
                        "book": bm["key"],
                        "market": mkt["key"],
                        "player_name": name,
                        "player_key": key[2],
                        "line": oc.get("point"),
                        "over_price": None,
                        "under_price": None,
                        # Standard markets carry the entry-level payout table, not a
                        # per-pick multiplier. Non-default multipliers live in the
                        # _alternate markets, which week 2 adds.
                        "multiplier": None,
                        "source_updated_at": _ts(mkt.get("last_update") or bm.get("last_update")),
                    },
                )
                row[f"{side}_price"] = oc.get("price")
    return list(rows.values())


def run_ingest(
    con: duckdb.DuckDBPyConnection,
    client: OddsApiClient,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[str, pl.DataFrame]:
    captured_at = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")

    events = client.events(captured_at, captured_at + timedelta(days=settings.days_ahead))
    log.info("%d upcoming events", len(events))

    rows: list[dict] = []
    for ev in events:
        try:
            odds = client.event_odds(ev["id"], list(settings.markets), list(settings.all_books))
        except Exception as exc:  # one bad event shouldn't sink the run
            log.warning("event %s failed: %s", ev.get("id"), exc)
            continue
        rows.extend(normalize_event_odds(odds, run_id, captured_at))

    df = pl.DataFrame(rows, schema=SNAPSHOT_SCHEMA)

    con.register("snap_df", df.to_arrow())
    con.execute("INSERT INTO prop_snapshots SELECT * FROM snap_df")
    con.unregister("snap_df")
    con.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
        [run_id, captured_at, len(events), df.height, client.usage.last_cost, client.usage.remaining],
    )

    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(settings.snapshot_dir / f"{run_id}.parquet")
    log.info(
        "run %s: %d rows, cost %s credits, %s remaining",
        run_id, df.height, client.usage.last_cost, client.usage.remaining,
    )
    return run_id, df
