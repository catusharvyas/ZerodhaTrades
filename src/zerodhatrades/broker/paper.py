"""Paper broker: real or fake market data, simulated fills at LTP. Nothing reaches the exchange."""
from __future__ import annotations

import itertools

from ..models import Order
from .base import MarketData


class PaperBroker:
    def __init__(self, data: MarketData):
        self._data = data
        self._ids = itertools.count(1)
        self.orders: list[tuple[str, Order, float]] = []

    def ltp(self, symbol: str, exchange: str) -> float:
        return self._data.ltp(symbol, exchange)

    def closes(self, symbol: str, exchange: str, interval: str, count: int) -> list[float]:
        return self._data.closes(symbol, exchange, interval, count)

    def place_order(self, order: Order) -> str:
        oid = f"PAPER-{next(self._ids)}"
        self.orders.append((oid, order, self.ltp(order.symbol, order.exchange)))
        return oid
