"""Local dashboard (stdlib only): binds to 127.0.0.1; the only action is the kill switch."""
from __future__ import annotations

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

from .config import AppConfig
from .engine import IST

MAX_EVENTS = 200


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def build_state(cfg: AppConfig, now: datetime) -> dict:
    state_dir = Path(cfg.state_dir)
    positions = _read_json(state_dir / "positions.json", {}).get("positions", {})
    events: list[dict] = []
    log = Path(cfg.log_dir) / f"audit-{now.date().isoformat()}.jsonl"
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    day_pnl = next((e["day_pnl"] for e in reversed(events) if e.get("event") == "exit"), 0.0)
    beat = _read_json(state_dir / "heartbeat.json", {})
    age = None
    if beat.get("ts"):
        age = (now - datetime.fromisoformat(beat["ts"])).total_seconds()
    r = cfg.risk
    return {
        "now": now.isoformat(),
        "mode": cfg.mode,
        "kill_switch": Path(cfg.kill_switch_file).exists(),
        "halted": day_pnl <= -r.max_daily_loss,
        "heartbeat_age_s": age,
        "poll_interval_s": cfg.poll_interval_seconds,
        "day_pnl": day_pnl,
        "risk": {
            "max_daily_loss": r.max_daily_loss, "max_open_positions": r.max_open_positions,
            "window": f"{r.trading_window.start:%H:%M}-{r.trading_window.end:%H:%M}",
            "square_off": f"{r.square_off_time:%H:%M}", "allowed": r.allowed_symbols,
        },
        "positions": list(positions.values()),
        "events": events[-MAX_EVENTS:][::-1],
    }


def set_kill_switch(cfg: AppConfig, on: bool) -> None:
    path = Path(cfg.kill_switch_file)
    if on:
        path.touch()
    else:
        path.unlink(missing_ok=True)


def make_handler(cfg: AppConfig):
    page = resources.files("zerodhatrades").joinpath("dashboard.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def _host_ok(self) -> bool:  # blocks DNS-rebinding style access
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return self._send(403, b"forbidden", "text/plain")
            if self.path == "/api/state":
                body = json.dumps(build_state(cfg, datetime.now(IST))).encode()
                return self._send(200, body, "application/json")
            if self.path in ("/", "/index.html"):
                return self._send(200, page, "text/html; charset=utf-8")
            self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            if not self._host_ok() or self.headers.get("X-ZT") != "1" or self.path != "/api/kill":
                return self._send(403, b"forbidden", "text/plain")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                on = bool(json.loads(self.rfile.read(length))["on"])
            except (ValueError, KeyError, TypeError):
                return self._send(400, b"bad request", "text/plain")
            set_kill_switch(cfg, on)
            self._send(200, json.dumps({"kill_switch": on}).encode(), "application/json")

        def log_message(self, *args):  # keep the terminal quiet
            pass

    return Handler


def serve(cfg: AppConfig, port: int = 8765) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cfg))
    print(f"Dashboard: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
