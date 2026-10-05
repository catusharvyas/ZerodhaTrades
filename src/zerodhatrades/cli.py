from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from .auth import api_key, load_access_token, login
from .broker.kite import KiteBroker, KiteData
from .broker.paper import PaperBroker
from .config import load_config
from .engine import Engine


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    p = argparse.ArgumentParser(prog="zt")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="Daily Kite login; stores today's access token")
    chk = sub.add_parser("check-config", help="Validate a config file")
    chk.add_argument("--config", default="config/strategies.yaml")
    run = sub.add_parser("run", help="Run the engine")
    run.add_argument("--config", default="config/strategies.yaml")
    run.add_argument("--live", action="store_true", help="Send REAL orders")
    run.add_argument("--once", action="store_true", help="Run a single tick and exit")
    args = p.parse_args(argv)

    if args.cmd == "login":
        login()
        return
    cfg = load_config(args.config)
    if args.cmd == "check-config":
        print(f"OK: {len(cfg.strategies)} strategies, mode={cfg.mode}")
        return

    live = args.live and cfg.mode == "live"
    if args.live and cfg.mode != "live":
        raise SystemExit("--live given but config mode is not 'live'. Refusing.")
    if cfg.mode == "live" and not args.live:
        raise SystemExit("Config mode is 'live' but --live not given. Refusing.")
    if live and os.environ.get("ZT_CONFIRM_LIVE") != "YES":
        raise SystemExit("Live trading needs ZT_CONFIRM_LIVE=YES in the environment.")

    token = load_access_token()
    broker = KiteBroker(api_key(), token) if live else PaperBroker(KiteData(api_key(), token))
    print(f"Starting engine in {'LIVE' if live else 'PAPER'} mode")
    Engine(cfg, broker).run(once=args.once)
