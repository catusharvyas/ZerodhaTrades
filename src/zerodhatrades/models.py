from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    symbol: str
    exchange: str
    side: str          # BUY | SELL
    quantity: int
    product: str = "MIS"
    tag: str = ""


@dataclass
class Position:
    strategy: str
    symbol: str
    exchange: str
    side: str
    quantity: int
    product: str
    entry_price: float
    stop_loss: float
    target: float

    @property
    def exit_side(self) -> str:
        return "SELL" if self.side == "BUY" else "BUY"

    def pnl(self, price: float) -> float:
        sign = 1 if self.side == "BUY" else -1
        return (price - self.entry_price) * self.quantity * sign
