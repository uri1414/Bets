"""Settings shared by every module. Thresholds marked "tune" come from SPEC.md and
are meant to be revisited in backtest."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SPORT = "americanfootball_nfl"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Book keys as The Odds API names them.
UNDERDOG = "underdog"
SHARP_BOOKS = ("pinnacle", "betonlineag", "lowvig", "novig", "prophetx")
# FanDuel/DraftKings: consensus check only, never part of the sharp prior (SPEC §1.1).
CONSENSUS_BOOKS = ("fanduel", "draftkings")

# Over/under player markets. Anytime-TD style yes/no markets are left out on purpose.
MARKETS = (
    "player_pass_yds",
    "player_pass_attempts",
    "player_pass_completions",
    "player_pass_tds",
    "player_rush_yds",
    "player_rush_attempts",
    "player_reception_yds",
    "player_receptions",
    "player_rush_reception_yds",
)

# Placeholder line-conversion settings, used until the projection model (week 3)
# supplies a real per-player distribution (SPEC §1.3).
#   dist: "normal" with a fixed sd, or "poisson" for low counts
#   max_gap: largest sharp-vs-Underdog line gap we are willing to convert across
LINE_CONVERSION = {
    "player_pass_yds": {"dist": "normal", "sd": 55.0, "max_gap": 15.0},
    "player_pass_attempts": {"dist": "normal", "sd": 5.5, "max_gap": 3.0},
    "player_pass_completions": {"dist": "normal", "sd": 4.5, "max_gap": 2.0},
    "player_pass_tds": {"dist": "poisson", "max_gap": 0.0},
    "player_rush_yds": {"dist": "normal", "sd": 22.0, "max_gap": 10.0},
    "player_rush_attempts": {"dist": "normal", "sd": 3.8, "max_gap": 2.0},
    "player_reception_yds": {"dist": "normal", "sd": 24.0, "max_gap": 10.0},
    "player_receptions": {"dist": "poisson", "max_gap": 1.0},
    "player_rush_reception_yds": {"dist": "normal", "sd": 28.0, "max_gap": 10.0},
}

# Standard all-or-nothing payouts (SPEC §3). Week 2 replaces this with the live table.
STANDARD_PAYOUTS = {2: 3.0, 3: 6.0, 4: 10.0, 5: 20.0}


@dataclass(frozen=True)
class Settings:
    api_key: str | None = field(default_factory=lambda: os.environ.get("ODDS_API_KEY"))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("PROP_ENGINE_DATA", "data")))
    days_ahead: int = 7
    markets: tuple[str, ...] = MARKETS
    sharp_books: tuple[str, ...] = SHARP_BOOKS
    consensus_books: tuple[str, ...] = CONSENSUS_BOOKS
    # SPEC §3: a leg must clear the 5-pick floor by a margin. Tune.
    leg_floor: float = 0.54
    leg_margin: float = 0.02
    # SPEC §3 hard reject: lines older than 15 minutes vs the sharp feed.
    max_staleness_min: float = 15.0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "prop_engine.duckdb"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def all_books(self) -> tuple[str, ...]:
        return (UNDERDOG, *self.sharp_books, *self.consensus_books)
