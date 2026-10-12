"""Thin client for The Odds API v4 (https://the-odds-api.com/liveapi/guides/v4/)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from .config import ODDS_API_BASE, SPORT

log = logging.getLogger(__name__)


@dataclass
class Usage:
    used: int | None = None
    remaining: int | None = None
    last_cost: int = 0

    def update(self, headers: httpx.Headers) -> None:
        def as_int(name: str) -> int | None:
            value = headers.get(name)
            return int(float(value)) if value is not None else None

        self.used = as_int("x-requests-used")
        self.remaining = as_int("x-requests-remaining")
        self.last_cost += as_int("x-requests-last") or 0


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OddsApiClient:
    def __init__(self, api_key: str, client: httpx.Client | None = None, base_url: str = ODDS_API_BASE):
        if not api_key:
            raise ValueError("ODDS_API_KEY is not set")
        self.api_key = api_key
        self.base_url = base_url
        self.http = client or httpx.Client(timeout=30.0)
        self.usage = Usage()

    def _get(self, path: str, **params) -> object:
        params = {"apiKey": self.api_key, **{k: v for k, v in params.items() if v is not None}}
        resp = self.http.get(f"{self.base_url}{path}", params=params)
        self.usage.update(resp.headers)
        resp.raise_for_status()
        return resp.json()

    def events(self, start: datetime, end: datetime) -> list[dict]:
        """Upcoming events. Free: does not use credits."""
        return self._get(
            f"/sports/{SPORT}/events",
            commenceTimeFrom=_iso(start),
            commenceTimeTo=_iso(end),
            dateFormat="iso",
        )

    def event_odds(self, event_id: str, markets: list[str], bookmakers: list[str]) -> dict:
        """Player props for one event. Passing bookmakers (<=10) bills as one region."""
        if len(bookmakers) > 10:
            log.warning("%d bookmakers bill as more than one region", len(bookmakers))
        return self._get(
            f"/sports/{SPORT}/events/{event_id}/odds",
            markets=",".join(markets),
            bookmakers=",".join(bookmakers),
            oddsFormat="decimal",
            dateFormat="iso",
        )
