"""Fixtures shaped like The Odds API v4 /events and /events/{id}/odds responses."""

from datetime import datetime, timezone

import pytest

CAPTURED = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)
KICKOFF = "2026-10-18T17:00:00Z"


def outcomes(player, line, over, under):
    return [
        {"name": "Over", "description": player, "price": over, "point": line},
        {"name": "Under", "description": player, "price": under, "point": line},
    ]


def book(key, markets):
    return {
        "key": key,
        "title": key,
        "last_update": "2026-10-15T17:58:00Z",
        "markets": [
            {"key": mkey, "last_update": "2026-10-15T17:58:00Z", "outcomes": outs}
            for mkey, outs in markets.items()
        ],
    }


EVENT = {
    "id": "evt1",
    "sport_key": "americanfootball_nfl",
    "commence_time": KICKOFF,
    "home_team": "Kansas City Chiefs",
    "away_team": "Buffalo Bills",
}

EVENT_ODDS = {
    **EVENT,
    "bookmakers": [
        # Underdog: lines only, prices are placeholders for standard picks.
        book("underdog", {
            "player_reception_yds": outcomes("Travis Kelce", 66.5, 1.82, 1.82),
            "player_rush_yds": outcomes("James Cook", 70.5, 1.82, 1.82),
            "player_pass_tds": outcomes("Josh Allen", 1.5, 1.82, 1.82),
            "player_receptions": outcomes("Khalil Shakir", 4.5, 1.82, 1.82),
        }),
        # Sharp: Kelce 64.5 (needs conversion), Cook same line, strong Under.
        book("pinnacle", {
            "player_reception_yds": outcomes("Travis Kelce", 64.5, 1.87, 1.95),
            "player_rush_yds": outcomes("James Cook", 70.5, 2.25, 1.65),
            "player_pass_tds": outcomes("Josh Allen", 1.5, 1.90, 1.90),
        }),
        book("betonlineag", {
            "player_reception_yds": outcomes("Travis Kelce", 64.5, 1.85, 1.97),
            "player_rush_yds": outcomes("James Cook", 70.5, 2.20, 1.68),
            # One-sided quote: unusable.
            "player_pass_tds": [{"name": "Over", "description": "Josh Allen", "price": 1.9, "point": 1.5}],
        }),
        book("fanduel", {
            "player_rush_yds": outcomes("James Cook", 69.5, 2.0, 1.76),
        }),
    ],
}


@pytest.fixture
def captured():
    return CAPTURED


@pytest.fixture
def event_odds():
    return EVENT_ODDS


@pytest.fixture
def event():
    return EVENT
