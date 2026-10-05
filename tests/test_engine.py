from datetime import datetime

import pytest

from zerodhatrades.broker.paper import PaperBroker
from zerodhatrades.config import AppConfig
from zerodhatrades.engine import IST, Engine
from zerodhatrades.indicators import rsi, sma


class FakeData:
    def __init__(self, closes, price):
        self._closes, self.price = closes, price

    def ltp(self, symbol, exchange):
        return self.price

    def closes(self, symbol, exchange, interval, count):
        return self._closes


def make_cfg(tmp_path, **risk):
    base_risk = {
        "max_daily_loss": 1000, "max_order_value": 50000, "max_open_positions": 2,
        "max_orders_per_minute": 5, "allowed_symbols": ["INFY"],
        "trading_window": {"start": "09:20", "end": "15:00"}, "square_off_time": "15:15"}
    base_risk.update(risk)
    return AppConfig.model_validate({
        "state_dir": str(tmp_path / "state"), "log_dir": str(tmp_path / "logs"),
        "kill_switch_file": str(tmp_path / "KILL"), "risk": base_risk,
        "strategies": [{"name": "t", "symbol": "INFY", "side": "BUY", "quantity": 10,
                        "stop_loss_pct": 1, "target_pct": 2,
                        "entry": [{"type": "price_above", "value": 100}]}]})


def at(h, m):
    return datetime(2026, 10, 5, h, m, tzinfo=IST)


def test_entry_then_target_exit(tmp_path):
    data = FakeData([101.0], 1000.0)
    broker = PaperBroker(data)
    eng = Engine(make_cfg(tmp_path), broker)
    eng.tick(at(10, 0))
    assert "INFY" in eng.positions and len(broker.orders) == 1
    data.price = 1020.0  # +2% target
    eng.tick(at(10, 5))
    assert not eng.positions and len(broker.orders) == 2
    assert eng.risk.realized_pnl == pytest.approx(200.0)


def test_stop_loss_halts_on_daily_limit(tmp_path):
    data = FakeData([101.0], 1000.0)
    eng = Engine(make_cfg(tmp_path, max_daily_loss=50), PaperBroker(data))
    eng.tick(at(10, 0))
    data.price = 989.0  # below 1% SL => -110
    eng.tick(at(10, 5))
    assert eng.risk.halted and not eng.positions
    eng.tick(at(10, 10))
    assert not eng.positions  # no re-entry after halt


def test_outside_window_and_value_cap_block_entry(tmp_path):
    broker = PaperBroker(FakeData([101.0], 1000.0))
    Engine(make_cfg(tmp_path), broker).tick(at(9, 0))
    assert not broker.orders
    eng = Engine(make_cfg(tmp_path, max_order_value=5000), broker)
    eng.tick(at(10, 0))
    assert not broker.orders


def test_kill_switch_squares_off(tmp_path):
    broker = PaperBroker(FakeData([101.0], 1000.0))
    eng = Engine(make_cfg(tmp_path), broker)
    eng.tick(at(10, 0))
    (tmp_path / "KILL").write_text("")
    eng.tick(at(10, 1))
    assert not eng.positions and len(broker.orders) == 2


def test_square_off_time(tmp_path):
    broker = PaperBroker(FakeData([101.0], 1000.0))
    eng = Engine(make_cfg(tmp_path), broker)
    eng.tick(at(14, 59))
    eng.tick(at(15, 16))
    assert not eng.positions


def test_state_survives_restart(tmp_path):
    cfg = make_cfg(tmp_path)
    Engine(cfg, PaperBroker(FakeData([101.0], 1000.0))).tick(at(10, 0))
    assert "INFY" in Engine(cfg, PaperBroker(FakeData([1.0], 1000.0))).positions


def test_indicators():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert rsi(list(range(1, 30)), 14) == 100.0
