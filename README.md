# ZerodhaTrades

Rule-driven trade automation on Zerodha via [Kite Connect](https://kite.trade). Strategies are
declared in YAML, every order passes a risk gate, and **paper trading is the default**.

> **Disclaimer:** This is a framework, not investment advice or a profitable strategy. Trading
> involves risk of loss. Verify Zerodha's and SEBI's current rules for API/algo trading
> (including static-IP and order-rate requirements) before going live.

## Architecture

```
config/strategies.yaml ─► Engine.tick() every N seconds
                            ├─ halt?  (kill file / daily-loss breach) ─► square off all
                            ├─ square-off time? ─► close MIS positions
                            ├─ exits: LTP vs stop-loss / target per open position
                            └─ entries: indicators(entry conditions) ─► RiskManager ─► Broker
Broker = PaperBroker (simulated fills, real data) | KiteBroker (real orders)
Audit  = logs/audit-YYYY-MM-DD.jsonl (signal, approval/rejection, entry, exit)
State  = state/positions.json (positions survive restarts)
```

| Module | Role |
|---|---|
| `config.py` | Validated YAML schema (pydantic) |
| `indicators.py` | `price_above/below`, `sma_cross_up/down`, `rsi_below/above` (AND-combined) |
| `risk.py` | Allowed symbols, trading window, max positions, max order value, order rate, daily-loss halt |
| `engine.py` | Tick loop, entries/exits, square-off, kill switch, persistence |
| `broker/` | `paper.py`, `kite.py`, `base.py` protocol |
| `auth.py` | Daily Kite login / token handling |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                              # add KITE_API_KEY / KITE_API_SECRET
cp config/strategies.example.yaml config/strategies.yaml
zt check-config
zt login                                           # every trading day
zt run                                             # paper mode
zt run --once                                      # single tick
```

## Dashboard

```bash
zt dashboard            # http://127.0.0.1:8765 — run alongside `zt run`
```

Shows mode, engine status/heartbeat, realised day P&L vs the loss limit, open positions with
stop-loss/target, and today's audit feed. The only action is the kill switch (confirm dialog).
It binds to localhost only, rejects foreign `Host` headers, and needs no extra dependencies.
It shows realised P&L and entry/SL/target levels, not live prices.

## Going live (deliberately hard)

All three are required: `mode: live` in the config, `--live` on the command line, and
`ZT_CONFIRM_LIVE=YES` in the environment. Run paper for several weeks first and review
`logs/audit-*.jsonl`.

**Kill switch:** `touch KILL` — the next tick halts entries and squares off all positions.

## Known limitations

- Exits are **polled** (stop-loss/target checked each tick), not exchange-resident SL orders, so
  gaps or outages can slip past them. Adding Kite GTT/SL-M orders is the next hardening step.
- Orders are market orders; fills in paper mode are at LTP with no slippage or costs.
- Kite requires a manual login each day; the token cannot be fully automated.
- Entry conditions are evaluated on the latest (possibly forming) candle.

## Roadmap

Backtest/replay harness, WebSocket ticks, exchange-side SL orders, costs/slippage model,
alerts (Telegram/email), additional indicators.

## Development

```bash
ruff check . && pytest -q
```
