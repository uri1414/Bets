"""Markdown slate report (SPEC §9 report contract, week-1 subset)."""

from __future__ import annotations

from datetime import datetime

import polars as pl

from .config import STANDARD_PAYOUTS, Settings
from .devig import per_leg_break_even

MARKET_LABELS = {
    "player_pass_yds": "Pass yds",
    "player_pass_attempts": "Pass att",
    "player_pass_completions": "Completions",
    "player_pass_tds": "Pass TDs",
    "player_rush_yds": "Rush yds",
    "player_rush_attempts": "Rush att",
    "player_reception_yds": "Rec yds",
    "player_receptions": "Receptions",
    "player_rush_reception_yds": "Rush+rec yds",
}


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:.1f}%"


def _pts(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:+.1f}"


def render(matched: pl.DataFrame, run_id: str, captured_at: datetime, settings: Settings) -> str:
    lines = [f"# Slate report: run {run_id}", ""]
    lines.append(f"**Data freshness**: odds captured {captured_at:%Y-%m-%d %H:%M} UTC.")
    lines.append(
        "**Mode**: market-only (week 1). No projection model, no entries, no stakes yet."
    )
    lines.append("")

    games = matched.select("matchup", "commence_time").unique().sort("commence_time")
    lines.append("## Games")
    for g in games.iter_rows(named=True):
        kick = g["commence_time"].strftime("%a %m/%d %H:%M UTC") if g["commence_time"] else "?"
        lines.append(f"- {g['matchup']}, {kick}")
    lines.append("")

    lines.append("## Leg break-even (standard payouts)")
    lines.append("| Entry | Payout | Per-leg |")
    lines.append("| --- | --- | --- |")
    for legs, pay in STANDARD_PAYOUTS.items():
        lines.append(f"| {legs}-pick | {pay:g}x | {_pct(per_leg_break_even(pay, legs))} |")
    lines.append(
        f"\nA leg qualifies at {_pct(settings.leg_floor)} + {settings.leg_margin * 100:.0f} pts "
        f"= {_pct(settings.leg_floor + settings.leg_margin)} or better."
    )
    lines.append("")

    priced = matched.filter(pl.col("reject_reason").is_null())
    qual = priced.filter(pl.col("qualifies").is_not_null()).with_columns(
        pl.max_horizontal("edge_over", "edge_under").alias("best_edge")
    ).sort("best_edge", descending=True)

    lines.append(f"## Qualifying legs ({qual.height})")
    if qual.height == 0:
        lines.append("**PASS**: no leg clears the bar on the sharp prior.")
    else:
        lines.append(
            "| Player | Market | UD line | Pick | Sharp lines | P(higher) | P(lower) | Edge | FD/DK P(higher) | Game |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in qual.iter_rows(named=True):
            edge = r["edge_over"] if r["qualifies"] == "higher" else r["edge_under"]
            lines.append(
                f"| {r['player_name']} | {MARKET_LABELS.get(r['market'], r['market'])} | {r['ud_line']:g} "
                f"| **{r['qualifies'].upper()}** | {r['sharp_lines']} | {_pct(r['p_over'])} "
                f"| {_pct(r['p_under'])} | {_pts(edge)} | {_pct(r['consensus_over'])} | {r['matchup']} |"
            )
    lines.append("")

    lines.append("## Coverage")
    lines.append(f"- Underdog props seen: {matched.height}")
    lines.append(f"- Priced against sharp books: {priced.height}")
    lines.append(f"- Of those, line-converted: {priced.filter(pl.col('converted')).height}")
    rejects = (
        matched.filter(pl.col("reject_reason").is_not_null())
        .with_columns(pl.col("reject_reason").str.replace(r"^[a-z]+: ", "").str.replace(r"; .*$", ""))
        .group_by("reject_reason").len().sort("len", descending=True)
    )
    for r in rejects.head(8).iter_rows(named=True):
        lines.append(f"- Rejected ({r['reject_reason']}): {r['len']}")
    lines.append("")
    lines.append(
        "## Open data gaps\n"
        "- Line conversion uses placeholder distributions until the week-3 projection model.\n"
        "- Players are joined by normalized name, not nflverse id.\n"
        "- Injury scenarios are not modeled yet.\n"
    )
    lines.append(
        "_Decision support, not guaranteed wins. Even a sound model will PASS on most slates._"
    )
    return "\n".join(lines) + "\n"
