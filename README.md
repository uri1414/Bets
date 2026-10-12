# Bets: NFL Prop Engine v2

Finds Underdog player props that disagree with the devigged sharp-book market.
Full design: [docs/SPEC.md](docs/SPEC.md).

## Status

Week 1 of the build order (market side) is in place:

| Module | What it does |
| --- | --- |
| `ingest_odds` | Pulls Underdog + sharp + FanDuel/DraftKings player props from The Odds API and stores a timestamped snapshot (DuckDB + Parquet). |
| `match_props` | Joins each Underdog prop to the sharp books by game, market and player; prices Higher and Lower; flags legs that clear 54% + 2 pts. |
| `devig` | Multiplicative and power no-vig probabilities (keeps the lower of the two per side) and sharp-to-Underdog line conversion. |
| `report` | Markdown slate report: freshness, games, qualifying legs or PASS, coverage, open gaps. |

Not built yet: entry optimizer and live payout table (week 2), stats ingest and projections (weeks 3–4), blend, sizing and CLV tracker (week 5).

## Setup

```bash
pip install -e ".[dev]"
export ODDS_API_KEY=...   # https://the-odds-api.com, 100K-credit plan to start
```

## Usage

```bash
python -m prop_engine run              # ingest, then match + report
python -m prop_engine ingest --days 7  # snapshot only (run on the SPEC §5 schedule)
python -m prop_engine match            # re-price the latest snapshot -> reports/slate_<run>.md
```

Data goes to `data/` (override with `--data-dir` or `PROP_ENGINE_DATA`). Each ingest
call costs about 9 markets × 1 region credits per game. Books are requested by key
(8 of them, so they bill as one region).

## Tests

```bash
python -m pytest
```

## Known limitations

- **Line conversion is a placeholder.** When the sharp line differs from Underdog's, it fits a
  normal (yards, attempts) or Poisson (receptions, pass TDs) distribution to the sharp price.
  Gaps beyond a per-market max are rejected. Week 3 replaces this with the player's projected distribution.
- **Staleness check** rejects props when the snapshot is more than 15 minutes old at match time.
- **Players are joined by normalized name**, not nflverse ID.
- **Underdog multipliers**: standard markets are stored without a per-pick multiplier.
  Non-default multipliers (`_alternate` markets) come in week 2.
- **Unverified against a live response**: the API client follows the documented v4 response
  shape. Check the first real snapshot, especially Underdog's outcome format.
