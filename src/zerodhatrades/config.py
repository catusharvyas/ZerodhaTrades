"""Typed, validated configuration loaded from YAML."""
from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

ConditionType = Literal["price_above", "price_below", "sma_cross_up", "sma_cross_down",
                        "rsi_below", "rsi_above"]


def _parse_hhmm(v: str) -> time:
    h, m = v.split(":")
    return time(int(h), int(m))


class Condition(BaseModel):
    type: ConditionType
    fast: int | None = None
    slow: int | None = None
    period: int | None = None
    value: float | None = None

    @model_validator(mode="after")
    def _check_params(self) -> Condition:
        if self.type.startswith("sma_cross"):
            if not (self.fast and self.slow) or self.fast >= self.slow:
                raise ValueError(f"{self.type} needs fast < slow")
        elif self.type.startswith("rsi"):
            if not self.period or self.value is None:
                raise ValueError(f"{self.type} needs period and value")
        elif self.value is None:
            raise ValueError(f"{self.type} needs value")
        return self


class Strategy(BaseModel):
    name: str
    symbol: str
    exchange: Literal["NSE", "BSE", "NFO"] = "NSE"
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    product: Literal["MIS", "CNC", "NRML"] = "MIS"
    interval: str = "5minute"
    max_trades_per_day: int = Field(default=1, gt=0)
    stop_loss_pct: float = Field(gt=0)
    target_pct: float = Field(gt=0)
    entry: list[Condition] = Field(min_length=1)


class TradingWindow(BaseModel):
    start: time
    end: time

    @field_validator("start", "end", mode="before")
    @classmethod
    def _t(cls, v):
        return _parse_hhmm(v) if isinstance(v, str) else v


class RiskConfig(BaseModel):
    max_daily_loss: float = Field(gt=0)
    max_order_value: float = Field(gt=0)
    max_open_positions: int = Field(gt=0)
    max_orders_per_minute: int = Field(gt=0)
    allowed_symbols: list[str] = Field(min_length=1)
    trading_window: TradingWindow
    square_off_time: time

    @field_validator("square_off_time", mode="before")
    @classmethod
    def _t(cls, v):
        return _parse_hhmm(v) if isinstance(v, str) else v


class AppConfig(BaseModel):
    mode: Literal["paper", "live"] = "paper"
    poll_interval_seconds: int = Field(default=30, ge=5)
    kill_switch_file: str = "KILL"
    state_dir: str = "state"
    log_dir: str = "logs"
    risk: RiskConfig
    strategies: list[Strategy] = Field(min_length=1)

    @model_validator(mode="after")
    def _symbols_allowed(self) -> AppConfig:
        allowed = set(self.risk.allowed_symbols)
        for s in self.strategies:
            if s.symbol not in allowed:
                raise ValueError(f"strategy {s.name}: {s.symbol} not in risk.allowed_symbols")
        return self


def load_config(path: str | Path) -> AppConfig:
    with open(path) as f:
        return AppConfig.model_validate(yaml.safe_load(f))
