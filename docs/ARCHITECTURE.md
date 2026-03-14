# System Architecture

```
┌─────────────────┐   ┌─────────────────┐
│ Data Collector  │   │ News Collector  │
│ (Gamma + CLOB)  │   │ (RSS)           │
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
│  Dashboard  │  │ (MA, RSI)   │  └────────┬────────┘
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

## Pipeline

Web API (FastAPI, `/docs`) reads data from DB and runs the **full pipeline** in background (default: every hour):

```
cleanup_stale_data()     – deduplicate trades (self-join DELETE)
       ↓
collector               – Gamma API → markets; CLOB auth or prices-history → trades; orderbook
       ↓                  Filters: only liquid markets (volume ≥ MIN_MARKET_VOLUME or active bid/ask)
news_collector          – RSS → keyword filter → news table (synchronous, no asyncio)
       ↓
feature_store           – trades → MA, RSI, MACD, volume, ROC → features
       ↓                  Prioritizes markets with orderbook data (liquid first)
ml_module               – features + target → walk-forward validation → signals
       ↓                  Skips flat-price markets (price_std < MIN_PRICE_STD)
backtester              – signals + prices → simulated P&L → results
```

### CLOB Authentication

The collector supports optional L2 authentication via `py-clob-client`:

| Mode | Config | What you get |
|------|--------|-------------|
| **No auth** (default) | Nothing needed | Public `prices-history` (price snapshots, all side="buy", size=1) |
| **L2 auth** | `POLYMARKET_PRIVATE_KEY` | Real trades from CLOB `/trades` (proper buy/sell sides, real sizes) |
| **L2 with pre-derived creds** | `POLYMARKET_PRIVATE_KEY` + `API_KEY/SECRET/PASSPHRASE` | Same, but skips credential derivation on startup |

### API Endpoints

| Path | Description |
|------|-------------|
| `GET /docs` | Swagger UI |
| `GET /dashboard` | Visual dashboard (Overview, Trading, Technical, Signals, Performance, News). Fetches market-specific data on selection |
| `GET /api/v1/markets` | Market list (limit, offset, with_signals) |
| `GET /api/v1/markets/{market_id}` | Single market |
| `GET /api/v1/trades` | Trades (market_id optional, limit, offset, after_id cursor) |
| `GET /api/v1/orderbook` | Order book snapshots (market_id optional) |
| `GET /api/v1/signals` | ML signals with signal_label (buy/hold/sell) |
| `GET /api/v1/features` | Computed features (market_id optional) |
| `GET /api/v1/news` | RSS news items |
| `GET /api/v1/results` | Backtest P&L results |
| `GET /api/v1/analytics` | Aggregated analytics: trade stats, feature correlations, signal distribution, PnL timeline, spread |
| `GET /api/v1/status` | DB counts, pipeline errors, migration status |

## Database Tables

| Table | Description | Key columns |
|-------|-------------|------------|
| `markets` | Market metadata | market_id (PK), question, slug, end_date, outcome_settled |
| `trades` | Trade/price data | market_id, ts, price, size, side |
| `orderbook` | Bid/ask snapshots | market_id, ts, bid_price, bid_qty, ask_price, ask_qty |
| `fee_rates` | Token fees | token_id (PK), base_fee_bps |
| `features` | Computed features | market_id, ts, feature_name, feature_value |
| `news` | RSS news | source, title, link, summary |
| `signals` | ML predictions | market_id, ts, prediction |
| `orders` | Placed orders | order_id (PK), market_id, side, price, size, status |
| `results` | Backtest results | market_id, ts, profit, run_id |

Indexes: `(market_id, ts)` on trades, orderbook, features, signals, results. Trade dedup: `(market_id, ts, price)`.

### Migrations

Alembic migrations in `db/migrations/versions/`:
- `001` — initial schema (all tables)
- `002` — add slug to markets
- `003` — add indexes on signals and results
- `004` — add trade dedup index

## Features

- **Price**: ma_1h, ma_5m, volatility_1h, roc_1h, rsi_14, macd, macd_signal, macd_hist
- **Volume**: volume_1h, volume_5m
- **Spread** (when bid/ask available): spread, spread_bps, mid_price

## ML Signals

### Target Construction

Target = "will price go up within the next N periods?" (default N=5, configurable via `ML_TARGET_HORIZON`):
```
future_max = max(price[i+1], price[i+2], ..., price[i+N])
target = 1 if future_max > price[i] else 0
```

This produces a more balanced target than single-step (next price > current), especially for slow-moving prediction markets.

### Signal Thresholds (aligned with backtester)

| Prediction | Label | Action |
|-----------|-------|--------|
| ≥ 0.55 | **buy** | Open long position |
| 0.35–0.55 | **hold** | No action |
| < 0.35 | **sell** | Close position |

### Market Filtering

- Markets with `price_std < MIN_PRICE_STD` (default 0.002) are skipped — flat prices contain no signal
- Markets with orderbook data (liquid) are prioritized for training
- Single-class targets (all up or all down) are skipped

### Model Validation

- TimeSeriesSplit / walk-forward (no leakage)
- Train on first 80%, generate out-of-sample signals on last 20%
- Metrics logged: AUC, precision, recall, target balance

## Execution Bot

- Default: `POLYMARKET_DRY_RUN=true` — orders not sent
- Real trading: `POLYMARKET_DRY_RUN=false`, set `POLYMARKET_PRIVATE_KEY`
- Risk: Kelly criterion, position limits, stop-loss, take-profit
- `market_id` (condition_id) ≠ `token_id` — CLOB orders need token_id from Gamma API
