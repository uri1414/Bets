# NFL Prop Engine v2

Oct 12, 2026 · @Uriel Gonzalez

## Core principle

Start from the sharp market, find where Underdog disagrees with it, and only then use our own projection to confirm or veto. Rank by entry-level EV, size small, and PASS when nothing clears the bar.

Flow: matchup → player discovery → devigged sharp prior → opportunity × efficiency projection → injury/role adjustment → both directions priced against the real payout table → correlation-aware entries → fractional-Kelly sizing → log and grade on CLV.

| Area | v1 | v2 |
| --- | --- | --- |
| Starting point | Build projection from scratch | Devigged sharp-book line is the prior |
| Break-even | 1 / multiplier per leg | Solve on the full entry payout table |
| Correlation | Avoid correlated legs | Seek positive correlation where allowed |
| Ranking | Fixed 25/20/15 weighted score | Calibrated EV; quality factors become filters |
| Small samples | Recency weighting | Bayesian shrinkage to role baselines |
| Distributions | Median + 25–75% | Simulated joint team/player outcomes, skew-aware |
| Sizing | None | Fractional Kelly with per-game caps |
| Success metric | Hit rate / ROI | CLV first, ROI second |
| Scope | Snap-level script rebuild, man/zone | Neutral pass rate, pace, role shares first |

## 1. Market prior

The sharp-book price is the best single estimate of each prop's probability; our model adjusts from it, never ignores it.

1. Pull the same player, market and line from 2+ sharp or high-limit books (Pinnacle, Circa, BetOnline, plus FanDuel/DraftKings as a consensus check).
2. Remove the vig. Default to the power method; also compute multiplicative and use the more conservative of the two. Juice is usually loaded on the Over in player props, so naive devigging overstates Over probability.
3. Lines differ from Underdog's (e.g., 64.5 vs 66.5 yards)? Convert using the player's projected distribution: P(over 66.5) = P(over 64.5) − P(65 ≤ X ≤ 66).
4. Blend: final probability = w × market + (1 − w) × model. Start with w = 0.7 for markets with 2+ sharp books, 0.5 with one book, and skip markets with no sharp price. Tune w in backtest.
5. Flag a play only when the market alone, or the blend, clears break-even (section 3). Model-only edges against the market are logged, not bet, until the backtest proves the model beats the close.

## 2. Player projection model

Project opportunity first, efficiency second, and simulate the team and its players together so totals stay consistent.

**Team layer (per simulation)**

- Plays: from both teams' pace (neutral-script seconds per play) and the game total/spread.
- Pass rate: neutral-script pass rate over expected, adjusted by simulated score state. Use win probability buckets, not final margin.
- Inputs kept: neutral pass rate, pace, early-down pass rate, red-zone trips, pressure rate allowed vs opponent pressure rate. Snap-level script rebuilds and man/zone splits are phase-2, added only if they improve backtest calibration.

**Player layer**

- Opportunity shares: route share, target share (per route run), carry share, red-zone share, designed QB runs.
- Efficiency: catch rate, yards per reception, yards per carry, TD rate.
- Shrinkage: each rate is a Bayesian estimate pulled toward the player's role baseline (e.g., WR2 in a 3-WR offense). Weight = games played; a 3-game sample leans mostly on the prior.
- Recency: exponential decay with a half-life of about 6 games; tune in backtest.

**Distributions**

- Targets, receptions, carries, attempts: count models (binomial on opportunities, overdispersed where needed).
- Yards: per-touch yards drawn from a skewed distribution, summed per touch. This produces the natural zero-inflation and long right tail.
- Run 10,000+ game simulations. Output mean, median, 10/25/75/90 percentiles and P(over) at every line. Use the median vs line for direction; overs on yardage often have a mean above the median.

**Injuries and roles**

- Pull a chronological injury log for both rosters. Tag each historical game with who was out.
- Re-estimate shares only from games with comparable personnel. With fewer than 3 such games, redistribute vacated targets by position-role priors, never one-for-one.
- At lock, re-run with the official inactives. Unclear status = scenario-weighted (active/inactive) or skip.

## 3. Pricing: entry-level EV

Price the whole entry, not the leg. With standard all-or-nothing payouts, each leg must hit about 55–58% just to break even ([payout source](https://www.squawka.com/us/?p=2895)).

| Standard entry | Payout | Per-leg break-even |
| --- | --- | --- |
| 2-pick | 3x | 57.7% |
| 3-pick | 6x | 55.0% |
| 4-pick | 10x | 56.2% |
| 5-pick | 20x | 54.9% |

Per-leg break-even = (1 / payout)^(1 / legs), valid only for independent legs at equal probability. Payouts vary by state and Underdog adjusts some picks' multipliers, so the engine reads the live table from the app at capture time instead of hard-coding it.

**EV calculation**

```latex
EV = \sum_{k} P(k \text{ correct}) \times \text{payout}(k) - 1
```

- Get P(k correct) from the joint simulation (section 2), not by multiplying leg probabilities. That way correlation is priced automatically.
- Flex (Pick8) entries: use the same formula with the partial-payout ladder ([flex payouts](https://rotogrinders.com/sports-betting/underdog-fantasy/flex)).
- Pushes/voids: apply the platform rule (entry re-prices down a leg) inside the simulation.
- Price both Higher and Lower for every line. Keep a leg only if its blended probability clears 54% (the 5-pick floor) with a margin of 2+ points; tune the margin in backtest.

**Hard rejects**: lines older than 15 minutes vs the sharp feed, players with unresolved status, markets with no sharp price, samples under 4 relevant games with no usable prior.

## 4. Correlation and entry construction

Payouts assume independent legs, so positively correlated legs raise entry EV and negatively correlated legs lower it. Build entries to exploit that, within what the platform allows.

| Pair | Correlation | Use |
| --- | --- | --- |
| QB pass yds Higher + his WR1 rec yds Higher | Strong + | Stack |
| QB pass yds Higher + opposing QB pass yds Higher | Moderate + (shootout) | Stack in high totals |
| RB rush att Higher + team favored, QB pass att Lower | + (positive script) | Stack |
| WR1 rec yds Higher + WR2 rec yds Higher, same team | Weak or − (target competition) | Avoid |
| RB rush yds Higher + opposing QB pass yds Lower | Mild + | Optional |

1. Estimate pair correlations from the joint simulation, not from rules of thumb; the table above is the expected sign.
2. Search entries with an optimizer: maximize EV over all 2–5 leg combinations of qualifying legs, subject to platform restrictions on same-game picks.
3. Diversify across entries: cap exposure to any one player at 30% of the slate's entries and any one game at 50%.
4. No qualifying legs = PASS. Never fill an entry with a coin-flip leg to reach a bigger multiplier.

## 5. Sizing and timing

Stake ¼ Kelly or less on entry EV, and run the model at the moments lines are most likely to be stale.

**Sizing**

- Kelly fraction for an entry = EV / (payout − 1) for all-or-nothing; use ¼ of it, capped at 2% of bankroll per entry.
- Total exposure per NFL slate: 10% of bankroll max; per game: 4%.
- Shrink the stake further when the edge relies mostly on the model rather than the market prior.

**Run schedule (Pacific time)**

| When | Why |
| --- | --- |
| Tuesday–Wednesday, after lines open | Early mispricing before sharp limits rise |
| Wednesday–Friday, after each practice report | Injury-driven role changes |
| Friday afternoon, after final injury reports (game statuses) | Questionable tags resolved |
| ~90 min before kickoff, at official inactives | Fastest edge: Underdog lags sharp books on late news |

Every run logs the sharp line and the Underdog line at capture time, so CLV can be graded at close.

## 6. Validation

A strategy is proven by beating the closing line, not by a hot month. ROI needs hundreds of entries to separate skill from variance; CLV shows up in weeks.

- Backtest walk-forward: train on weeks 1…n, predict week n+1, roll forward. Use strict as-of timestamps; nothing after capture time enters a prediction.
- Calibration: bucket predicted leg probabilities (52–54%, 54–56%, …) and compare to actual hit rates; report Brier score and log loss per market.
- CLV: for each leg, compare our capture probability to the devigged sharp close. Target: average positive CLV over 200+ legs before scaling stakes.
- Ablation: test each feature group (script, injuries, opponent) on/off. Keep only what improves calibration out of sample.
- Live tracking: record every recommended entry, including PASSes, with stake, EV, result and CLV.

## 7. Tech stack and AI coding model

Build in Python, store in DuckDB, model with a Bayesian library, and write the code with Claude Code.

| Layer | Pick | Why |
| --- | --- | --- |
| Language | Python 3.12 | Every NFL data and stats library lives here |
| Data frames | Polars | nflreadpy returns Polars; fast on full play-by-play |
| Storage | DuckDB (single file) + Parquet snapshots | Free, SQL, no server; snapshots give as-of history |
| Bayesian models | PyMC or NumPyro | Shrinkage of player rates toward role priors |
| Simulation | NumPy (vectorized) | 10,000 game sims in seconds |
| Optional ML | LightGBM | Only if it beats the Bayesian model in backtest |
| Scheduling | Cron or GitHub Actions | Runs at the times in section 5 |
| Output | Markdown/HTML report + a dashboard | Daily shortlist, CLV tracker |

**AI coding model**

- Use Claude Code with Claude Opus 5.5 for the architecture, modeling math and debugging; it handles multi-file Python projects and runs tests itself.
- Use Claude Sonnet 5.5 for routine work (ingest scripts, schema changes, report formatting) to save cost and time.
- Give it this doc as the spec, build one module at a time, and require a test for each before moving on.

## 8. Data sources

Two sources cover the core build for $59–119/month: nflverse (free) for stats and The Odds API for sharp and Underdog lines in one feed.

| Need | Source | Cost | Notes |
| --- | --- | --- | --- |
| Play-by-play, rosters, snaps, depth charts, injuries, schedules | [nflverse via nflreadpy](https://pypi.org/project/nflreadpy/) | Free | Python port of nflreadr, returns Polars; data mostly CC-BY 4.0 |
| Underdog lines + multipliers | [The Odds API](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html), region us_dfs | Paid plan | Non-default multipliers sit in _alternate markets; DFS odds are indicative |
| Sharp prior | Same API: Pinnacle (eu), BetOnline, LowVig (us), Novig/ProphetX (us_ex) | Same plan | Pinnacle comes from its public site and may be delayed |
| Consensus check | Same API: FanDuel, DraftKings | Same plan | Props are heavily juiced; devig before use |
| Historical odds for backtest | Same API, historical endpoint | Paid plans only | Snapshots back to 2020 |
| Route participation, charting | FTN (via nflverse) or paid charting sites | Free–paid | Phase 2 only |
| Weather | Open-Meteo or NWS | Free | Outdoor stadiums only |

[The Odds API plans](https://the-odds-api.com/): 20K credits $30/mo, 100K $59/mo, 5M $119/mo. Player props bill per market per region per event, so start on 100K and move to 5M once polling runs every few minutes near kickoff.

**Backup feed**: [PropLine](https://www.getapp.com/all-software/a/propline/) bills per request and carries Pinnacle and Underdog with payout multipliers, but its listed Pinnacle/FanDuel/DraftKings prop coverage did not include NFL as of its latest docs. Re-check before relying on it.

Underdog has no official public API; avoid scraping the app directly, which risks your account under its terms.

## 9. Pipeline, schema and build order

Build the market side first: it can find edges on day one, before the projection model exists.

**Modules**

1. `ingest_stats`: nflverse PBP, rosters, snaps, injuries → DuckDB, nightly.
2. `ingest_odds`: sharp + Underdog props, timestamped snapshot every run.
3. `match_props`: join Underdog and sharp lines by player, market and line.
4. `devig`: power and multiplicative no-vig probabilities; line conversion.
5. `features`: role shares, pace, neutral pass rate, injury context, as-of each game.
6. `projections`: Bayesian rates → joint game simulation → P(over) per line.
7. `blend`: market × model weights.
8. `entry_optimizer`: EV over 2–5 leg combos with payout table and correlation.
9. `sizing`: fractional Kelly with caps.
10. `report` + `tracker`: shortlist or PASS; log entries, results, CLV.

**Records**

- `PropSnapshot(player_id, game_id, book, market, line, over_price, under_price, multiplier, captured_at)`
- `NoVig(prop_id, method, p_over, p_under, books_used)`
- `PlayerGame(player_id, game_id, snaps, routes, targets, carries, yards, td, teammates_out[])`
- `Projection(player_id, game_id, market, mean, median, p10, p25, p75, p90, run_at)`
- `Leg(prop_id, direction, p_market, p_model, p_blend, edge)`
- `Entry(legs[], type, payout_table, ev, stake, result, clv)`

**Build order**

- [ ] Week 1: ingest_odds, match_props, devig. Start logging snapshots now; history can't be backfilled from live runs.
- [ ] Week 2: entry_optimizer with market-only probabilities; paper-trade and track CLV.
- [ ] Weeks 3–4: ingest_stats, features, projections; backtest on the historical endpoint.
- [ ] Week 5: blend, sizing, tracker; go live small only after positive paper CLV.

**Report contract (per slate)**: data freshness · games and kickoffs · qualifying legs with both directions, sharp vs Underdog line, p_blend, edge · recommended entries with EV and stake, or PASS · injury scenarios pending · open data gaps.

Treat outputs as decision support, not guaranteed wins; even a sound model will PASS on most slates.

## Sources

- [nflreadpy on PyPI](https://pypi.org/project/nflreadpy/)
- [The Odds API: plans](https://the-odds-api.com/)
- [The Odds API: bookmakers and DFS sites](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)
- [Underdog standard payouts (Squawka)](https://www.squawka.com/us/?p=2895)
- [Underdog flex payouts (RotoGrinders)](https://rotogrinders.com/sports-betting/underdog-fantasy/flex)
- [PropLine listing (GetApp)](https://www.getapp.com/all-software/a/propline/)
