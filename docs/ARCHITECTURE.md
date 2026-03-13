# System Architecture

```
┌─────────────────┐   ┌─────────────────┐
│ Data Collector  │   │ News Collector  │
│ (API + PMXT)    │   │ (RSS)           │
└────────┬────────┘   └────────┬────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │   PostgreSQL /      │
         │   SQLite            │
         └──────────┬──────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│  Web API    │  │ Feature     │  │   ML Module     │
│  FastAPI    │  │ Store       │  │ (LR, RF, XGB)   │
│  Swagger    │  │ (MA, RSI)   │  └────────┬────────┘
│  /api/v1/*  │  └──────┬──────┘           │
└─────────────┘         └──────────┬───────┘
                                   ▼
                        ┌─────────────────────┐
                        │    Backtester       │
                        │    Execution Bot    │
                        └──────────┬──────────┘
                                   ▼
                        ┌─────────────────────┐
                        │  Polymarket CLOB    │
                        │  (py-clob-client)   │
                        └─────────────────────┘
```

Web API (FastAPI, `/docs`) reads data from DB and runs the **full pipeline** in background: collector → feature_store → ml_module.

### API Endpoints

| Path | Description |
|------|-------------|
| `GET /docs` | Swagger UI |
| `GET /api/v1/markets` | Market list (limit, offset) |
| `GET /api/v1/markets/{market_id}` | Single market |
| `GET /api/v1/trades` | Trades (market_id optional, limit, offset) |
| `GET /api/v1/orderbook` | Order book snapshots (market_id optional, limit, offset) |
| `GET /api/v1/signals` | ML signals (market_id optional, limit, offset) |
| `GET /api/v1/status` | db_ok, counts (markets, trades, orderbook, features, signals), last_*_error |

## Database Tables

| Table | Description |
|-------|-------------|
| `markets` | Market metadata (question, end_date, outcome_settled) |
| `orderbook` | Order book snapshots (bid/ask, qty) |
| `trades` | Trades (price, size, side) |
| `fee_rates` | Token fees |
| `features` | Computed features (market_id, ts, feature_name, value) |
| `news` | RSS news (title, link, summary) |
| `signals` | Model signals (prediction) |
| `orders` | Our orders |
| `results` | Backtest results |

Indexes: `(market_id, ts)` on orderbook, trades, features.

## Features

- **Price**: ma_1h, ma_5m, volatility_1h, roc_1h, rsi_14, macd, macd_signal, macd_hist
- **Volume**: volume_1h, volume_5m
- **Liquidity**: spread, spread_bps (when bid/ask available)

## Backtester Signals

- `1` — buy (prediction ≥ 0.5)
- `0` — hold (0.3 ≤ prediction < 0.5)
- `-1` — sell (prediction < 0.3)

## Model Validation

- TimeSeriesSplit / walk-forward
- No leakage: train up to t, test on t+1..t+k
- If target has only one class (all prices up/down) — market skipped: `single class in target, skipping`

## Execution Bot

- Default: `POLYMARKET_DRY_RUN=true` — orders not sent
- Real trading: `POLYMARKET_DRY_RUN=false`, set `POLYMARKET_PRIVATE_KEY`
- `market_id` (condition_id) ≠ `token_id` — CLOB orders need token_id
