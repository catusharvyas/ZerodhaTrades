"""Pre-trade risk checks. Every order must pass RiskManager.check before reaching a broker."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import RiskConfig
from .models import Order


@dataclass(frozen=True)
class Decision:
    ok: bool
    reason: str = ""


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.realized_pnl = 0.0
        self.halted = False
        self._order_times: deque[datetime] = deque()

    def record_pnl(self, pnl: float) -> None:
        self.realized_pnl += pnl
        if self.realized_pnl <= -self.cfg.max_daily_loss:
            self.halted = True

    def check_entry(self, order: Order, price: float, open_positions: int,
                    now: datetime) -> Decision:
        c = self.cfg
        if self.halted:
            return Decision(False, "trading halted (daily loss limit)")
        if order.symbol not in c.allowed_symbols:
            return Decision(False, f"{order.symbol} not in allowed_symbols")
        w = c.trading_window
        if not (w.start <= now.time() <= w.end):
            return Decision(False, "outside trading window")
        if open_positions >= c.max_open_positions:
            return Decision(False, "max_open_positions reached")
        if order.quantity * price > c.max_order_value:
            return Decision(False, "order value exceeds max_order_value")
        if self._recent_orders(now) >= c.max_orders_per_minute:
            return Decision(False, "order rate limit")
        return Decision(True)

    def note_order(self, now: datetime) -> None:
        self._order_times.append(now)

    def _recent_orders(self, now: datetime) -> int:
        cutoff = now - timedelta(minutes=1)
        while self._order_times and self._order_times[0] < cutoff:
            self._order_times.popleft()
        return len(self._order_times)
