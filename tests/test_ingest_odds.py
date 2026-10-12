import httpx
import pytest

from prop_engine import db
from prop_engine.config import Settings
from prop_engine.ingest_odds import normalize_event_odds, run_ingest
from prop_engine.odds_api import OddsApiClient


def test_normalize_pairs_over_and_under(event_odds, captured):
    rows = normalize_event_odds(event_odds, "r1", captured)
    kelce = [r for r in rows if r["book"] == "pinnacle" and r["player_key"] == "travis kelce"]
    assert len(kelce) == 1
    r = kelce[0]
    assert (r["line"], r["over_price"], r["under_price"]) == (64.5, 1.87, 1.95)
    assert r["event_id"] == "evt1"
    assert r["commence_time"].isoformat() == "2026-10-18T17:00:00+00:00"

    one_sided = [r for r in rows if r["book"] == "betonlineag" and r["market"] == "player_pass_tds"]
    assert one_sided[0]["under_price"] is None


def test_run_ingest_with_mock_api(tmp_path, event, event_odds, captured):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        headers = {"x-requests-used": "40", "x-requests-remaining": "99960"}
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json=[event], headers={**headers, "x-requests-last": "0"})
        return httpx.Response(200, json=event_odds, headers={**headers, "x-requests-last": "9"})

    client = OddsApiClient("KEY", client=httpx.Client(transport=httpx.MockTransport(handler)))
    settings = Settings(api_key="KEY", data_dir=tmp_path)
    con = db.connect(settings.db_path)

    run_id, df = run_ingest(con, client, settings, now=captured)

    assert run_id == "20261015T180000Z"
    odds_req = calls[1]
    assert odds_req.url.params["oddsFormat"] == "decimal"
    assert "underdog" in odds_req.url.params["bookmakers"].split(",")
    assert "pinnacle" in odds_req.url.params["bookmakers"].split(",")
    assert odds_req.url.params["apiKey"] == "KEY"

    assert df.height == con.execute("SELECT count(*) FROM prop_snapshots").fetchone()[0] > 0
    run = con.execute("SELECT n_events, credits_used, credits_remaining FROM runs").fetchone()
    assert run == (1, 9, 99960)
    assert (settings.snapshot_dir / f"{run_id}.parquet").exists()


def test_failed_event_is_skipped(tmp_path, event, captured):
    def handler(request):
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json=[event])
        return httpx.Response(422, json={"message": "bad market"})

    client = OddsApiClient("KEY", client=httpx.Client(transport=httpx.MockTransport(handler)))
    settings = Settings(api_key="KEY", data_dir=tmp_path)
    con = db.connect(settings.db_path)
    _, df = run_ingest(con, client, settings, now=captured)
    assert df.height == 0


def test_missing_key():
    with pytest.raises(ValueError):
        OddsApiClient("")
