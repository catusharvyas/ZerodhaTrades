"""Kite Connect adapter. KiteData is read-only market data; KiteBroker also places real orders."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from kiteconnect import KiteConnect

from ..models import Order


class KiteData:
    def __init__(self, api_key: str, access_token: str):
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
        self._tokens: dict[tuple[str, str], int] = {}

    def ltp(self, symbol: str, exchange: str) -> float:
        key = f"{exchange}:{symbol}"
        return float(self.kite.ltp([key])[key]["last_price"])

    def _token(self, symbol: str, exchange: str) -> int:
        if (exchange, symbol) not in self._tokens:
            for ins in self.kite.instruments(exchange):
                self._tokens[(exchange, ins["tradingsymbol"])] = ins["instrument_token"]
        return self._tokens[(exchange, symbol)]

    def closes(self, symbol: str, exchange: str, interval: str, count: int) -> list[float]:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        candles = self.kite.historical_data(
            self._token(symbol, exchange), now - timedelta(days=10), now, interval)
        return [float(c["close"]) for c in candles][-count:]


class KiteBroker(KiteData):
    def place_order(self, order: Order) -> str:
        return str(self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR,
            exchange=order.exchange,
            tradingsymbol=order.symbol,
            transaction_type=order.side,
            quantity=order.quantity,
            product=order.product,
            order_type=self.kite.ORDER_TYPE_MARKET,
            tag=order.tag[:20],
        ))
