from __future__ import annotations

from typing import Protocol

from ..models import Order


class MarketData(Protocol):
    def ltp(self, symbol: str, exchange: str) -> float: ...

    def closes(self, symbol: str, exchange: str, interval: str, count: int) -> list[float]: ...


class Broker(MarketData, Protocol):
    def place_order(self, order: Order) -> str:
        """Place a market order and return the order id."""
        ...
