"""Command line: `python -m prop_engine {ingest,match,run}`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import db
from .config import Settings
from .ingest_odds import run_ingest
from .match_props import match_run
from .odds_api import OddsApiClient
from .report import render


def _ingest(con, settings: Settings) -> str:
    client = OddsApiClient(settings.api_key or "")
    run_id, _ = run_ingest(con, client, settings)
    return run_id


def _match(con, settings: Settings, run_id: str | None, out_dir: Path) -> Path:
    run_id = run_id or db.latest_run_id(con)
    if run_id is None:
        sys.exit("no ingest runs yet: run `python -m prop_engine ingest` first")
    captured_at = con.execute("SELECT captured_at FROM runs WHERE run_id = ?", [run_id]).fetchone()[0]
    matched = match_run(con, run_id, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"slate_{run_id}.md"
    path.write_text(render(matched, run_id, captured_at, settings))
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="prop_engine")
    parser.add_argument("--data-dir", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="snapshot sharp + Underdog props")
    p_ing.add_argument("--days", type=int, default=7, help="look-ahead window for games")

    p_match = sub.add_parser("match", help="devig, match and write the slate report")
    p_match.add_argument("--run-id", default=None, help="defaults to the latest run")
    p_match.add_argument("--out", type=Path, default=Path("reports"))

    p_run = sub.add_parser("run", help="ingest then match")
    p_run.add_argument("--days", type=int, default=7)
    p_run.add_argument("--out", type=Path, default=Path("reports"))

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    kwargs = {"days_ahead": getattr(args, "days", 7)}
    if args.data_dir:
        kwargs["data_dir"] = args.data_dir
    settings = Settings(**kwargs)
    con = db.connect(settings.db_path)

    if args.cmd == "ingest":
        print(_ingest(con, settings))
    elif args.cmd == "match":
        print(_match(con, settings, args.run_id, args.out))
    else:
        run_id = _ingest(con, settings)
        print(_match(con, settings, run_id, args.out))
