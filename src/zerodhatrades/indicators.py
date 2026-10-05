from __future__ import annotations

from .config import Condition


def sma(values: list[float], n: int, offset: int = 0) -> float | None:
    end = len(values) - offset
    if end < n:
        return None
    window = values[end - n:end]
    return sum(window) / n


def rsi(values: list[float], period: int) -> float | None:
    if len(values) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period + 1, len(values)):  # Wilder smoothing
        d = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def evaluate(cond: Condition, closes: list[float]) -> bool:
    """Evaluate one entry condition against close prices. Missing data => False."""
    if not closes:
        return False
    t = cond.type
    if t == "price_above":
        return closes[-1] > cond.value
    if t == "price_below":
        return closes[-1] < cond.value
    if t in ("sma_cross_up", "sma_cross_down"):
        f_now, s_now = sma(closes, cond.fast), sma(closes, cond.slow)
        f_prev, s_prev = sma(closes, cond.fast, 1), sma(closes, cond.slow, 1)
        if None in (f_now, s_now, f_prev, s_prev):
            return False
        if t == "sma_cross_up":
            return f_prev <= s_prev and f_now > s_now
        return f_prev >= s_prev and f_now < s_now
    r = rsi(closes, cond.period)
    if r is None:
        return False
    return r < cond.value if t == "rsi_below" else r > cond.value


def entry_signal(conds: list[Condition], closes: list[float]) -> bool:
    return all(evaluate(c, closes) for c in conds)
