"""Trading engine: each tick checks exits, then scans strategies for entries, via the risk gate."""
from __future__ import annotations

import json
import time as _time
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .audit import AuditLog
from .broker.base import Broker
from .config import AppConfig, Strategy
from .indicators import entry_signal
from .models import Order, Position
from .risk import RiskManager

IST = ZoneInfo("Asia/Kolkata")
CANDLES = 100


class Engine:
    def __init__(self, cfg: AppConfig, broker: Broker):
        self.cfg = cfg
        self.broker = broker
        self.risk = RiskManager(cfg.risk)
        self.audit = AuditLog(cfg.log_dir)
        self.positions: dict[str, Position] = {}
        self.trades: dict[str, int] = {}   # strategy name -> entries today
        self._trade_day = ""
        self._state_file = Path(cfg.state_dir) / "positions.json"
        self._load_state()

    # ---- persistence (so a restart does not orphan open positions) ----
    def _load_state(self) -> None:
        if self._state_file.exists():
            raw = json.loads(self._state_file.read_text())
            self.positions = {k: Position(**v) for k, v in raw["positions"].items()}
            self._trade_day, self.trades = raw.get("trade_day", ""), raw.get("trades", {})

    def _save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "trade_day": self._trade_day, "trades": self.trades}))

    def _heartbeat(self, now: datetime) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        (self._state_file.parent / "heartbeat.json").write_text(
            json.dumps({"ts": now.isoformat(), "mode": self.cfg.mode}))

    # ---- main loop ----
    def run(self, once: bool = False) -> None:
        while True:
            try:
                self.tick(datetime.now(IST))
            except Exception as exc:  # noqa: BLE001 - never die silently; keep positions managed
                self.audit.write("tick_error", datetime.now(IST), error=repr(exc))
            if once:
                return
            _time.sleep(self.cfg.poll_interval_seconds)

    def tick(self, now: datetime) -> None:
        self._heartbeat(now)
        if self._trade_day != now.date().isoformat():  # new day: reset counters (and P&L)
            self._trade_day, self.trades = now.date().isoformat(), {}
            self.risk.realized_pnl, self.risk.halted = 0.0, False
        if self.risk.halted or Path(self.cfg.kill_switch_file).exists():
            self.audit.write("halted", now, kill_file=Path(self.cfg.kill_switch_file).exists(),
                             realized_pnl=self.risk.realized_pnl)
            self._square_off_all(now, "halt")
            return
        if now.time() >= self.cfg.risk.square_off_time:
            self._square_off_all(now, "square_off_time")
            return
        self._check_exits(now)
        if not self.risk.halted:
            self._scan_entries(now)

    # ---- exits ----
    def _check_exits(self, now: datetime) -> None:
        for sym, pos in list(self.positions.items()):
            price = self.broker.ltp(pos.symbol, pos.exchange)
            long = pos.side == "BUY"
            hit_sl = price <= pos.stop_loss if long else price >= pos.stop_loss
            hit_tp = price >= pos.target if long else price <= pos.target
            if hit_sl or hit_tp:
                self._exit(sym, price, now, "stop_loss" if hit_sl else "target")

    def _square_off_all(self, now: datetime, reason: str) -> None:
        for sym, pos in list(self.positions.items()):
            self._exit(sym, self.broker.ltp(pos.symbol, pos.exchange), now, reason)

    def _exit(self, sym: str, price: float, now: datetime, reason: str) -> None:
        pos = self.positions[sym]
        order = Order(pos.symbol, pos.exchange, pos.exit_side, pos.quantity, pos.product,
                      tag=f"zt{uuid.uuid4().hex[:10]}")
        oid = self.broker.place_order(order)  # exits bypass entry checks by design
        pnl = pos.pnl(price)
        self.risk.record_pnl(pnl)
        del self.positions[sym]
        self._save_state()
        self.audit.write("exit", now, reason=reason, order_id=oid, order=asdict(order),
                         price=price, pnl=pnl, day_pnl=self.risk.realized_pnl)

    # ---- entries ----
    def _scan_entries(self, now: datetime) -> None:
        for strat in self.cfg.strategies:
            if strat.symbol in self.positions:
                continue
            if self.trades.get(strat.name, 0) >= strat.max_trades_per_day:
                continue
            closes = self.broker.closes(strat.symbol, strat.exchange, strat.interval, CANDLES)
            if not entry_signal(strat.entry, closes):
                continue
            self._enter(strat, now)

    def _enter(self, strat: Strategy, now: datetime) -> None:
        price = self.broker.ltp(strat.symbol, strat.exchange)
        order = Order(strat.symbol, strat.exchange, strat.side, strat.quantity, strat.product,
                      tag=f"zt{uuid.uuid4().hex[:10]}")
        decision = self.risk.check_entry(order, price, len(self.positions), now)
        self.audit.write("signal", now, strategy=strat.name, symbol=strat.symbol, price=price,
                         approved=decision.ok, reason=decision.reason)
        if not decision.ok:
            return
        oid = self.broker.place_order(order)
        self.risk.note_order(now)
        self.trades[strat.name] = self.trades.get(strat.name, 0) + 1
        sign = 1 if strat.side == "BUY" else -1
        self.positions[strat.symbol] = Position(
            strategy=strat.name, symbol=strat.symbol, exchange=strat.exchange, side=strat.side,
            quantity=strat.quantity, product=strat.product, entry_price=price,
            stop_loss=price * (1 - sign * strat.stop_loss_pct / 100),
            target=price * (1 + sign * strat.target_pct / 100))
        self._save_state()
        self.audit.write("entry", now, order_id=oid, order=asdict(order), price=price)
