"""Kite's access token expires daily and requires a manual login; this module isolates that flow."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kiteconnect import KiteConnect

TOKEN_FILE = Path(".token.json")
IST = ZoneInfo("Asia/Kolkata")


def _today() -> str:
    return datetime.now(IST).date().isoformat()


def _creds() -> tuple[str, str]:
    key, secret = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_API_SECRET")
    if not key or not secret:
        raise SystemExit("Set KITE_API_KEY and KITE_API_SECRET (see .env.example).")
    return key, secret


def login() -> None:
    key, secret = _creds()
    kite = KiteConnect(api_key=key)
    print("1. Open this URL and log in:\n  ", kite.login_url())
    print("2. After login you are redirected to your redirect URL with ?request_token=XXXX")
    request_token = input("Paste the request_token: ").strip()
    session = kite.generate_session(request_token, api_secret=secret)
    TOKEN_FILE.write_text(json.dumps(
        {"date": _today(), "access_token": session["access_token"]}))
    TOKEN_FILE.chmod(0o600)
    print("Access token saved (valid for today only).")


def load_access_token() -> str:
    if not TOKEN_FILE.exists():
        raise SystemExit("No token. Run `zt login` first.")
    data = json.loads(TOKEN_FILE.read_text())
    if data["date"] != _today():
        raise SystemExit("Token is from a previous day. Run `zt login` again.")
    return data["access_token"]


def api_key() -> str:
    return _creds()[0]
