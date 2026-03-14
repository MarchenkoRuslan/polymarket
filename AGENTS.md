# Agent Instructions

Guide for AI agent working with Polymarket Trading System project.

## Project Context

Automated system for trading on Polymarket prediction markets. Full pipeline: data cleanup → data collection (API + CLOB auth) → news (RSS) → feature calculation → ML models → backtesting → order execution (py-clob-client, dry-run by default).

## Service Structure and Responsibilities

| Service | Path | Task |
|---------|------|------|
| **Web API** | `api/` | FastAPI, Swagger UI (`/docs`), Dashboard (`/dashboard`). Endpoints: markets, trades, orderbook, signals, features, news, results, analytics, status. Lifespan: init_db + pipeline in background |
| Web Server | `server.py` | uvicorn + same FastAPI app. Pipeline in background. For Railway/production |
| Data Collector | `services/collector/` | Polymarket API (Gamma, CLOB with optional L2 auth), PMXT Parquet → `markets`, `trades`, `orderbook`. Filters to liquid markets only |
| News Collector | `services/news_collector/` | RSS (synchronous) → keyword filter → `news` table |
| Feature Store | `services/feature_store/` | MA, volatility, RSI, MACD, spread, volume → `features`. Prioritizes liquid markets |
| ML Module | `services/ml_module/` | LR, RF, XGBoost, walk-forward → signals in `signals`. Skips flat-price markets, uses multi-period target horizon |
| Backtester | `services/backtester/` | Simulation with fees, slippage. Signals: 1=buy, 0=hold, -1=sell |
| Execution Bot | `services/execution_bot/` | py-clob-client, risk management (Kelly, limits, stop-loss). Default dry_run |

## Pipeline Flow

```
cleanup_stale_data (dedup trades)
       ↓
   collector (Gamma API → markets; CLOB auth or prices-history → trades; orderbook)
       ↓
   news_collector (RSS feeds → news table)
       ↓
   feature_store (trades → MA, RSI, MACD, volume → features)
       ↓
   ml_module (features + target → walk-forward → signals)
       ↓
   backtester (signals + prices → simulated P&L → results)
```

Default interval: 1 hour (`COLLECT_INTERVAL_SEC=3600`).

## Database

- PostgreSQL / SQLite, connection via `DATABASE_URL`
- Schema: `db/schema_sqlite.sql` (local), migrations: `db/migrations/` (Alembic, 4 versions)
- Tables: `markets`, `orderbook`, `trades`, `fee_rates`, `features`, `news`, `signals`, `orders`, `results`
- Key indexes: `idx_trades_market_ts`, `idx_trades_dedup` (market_id, ts, price)

## Code Change Rules

1. **Import paths**: `sys.path.insert(0, project_root)` at entry points. Root — parent of `services/`.
2. **Config**: variables in `config/settings.py`, export in `config/__init__.py`. Add to both files + `.env.example`.
3. **Linting**: ruff (`ruff.toml`), Python 3.11+.
4. **Backtester**: when changing logic, verify fees (30 bps) and slippage.
5. **ML validation**: walk-forward / TimeSeriesSplit only, no future leakage. Target uses multi-period horizon (`ML_TARGET_HORIZON`).
6. **Mutations**: do not mutate input structures (e.g. in `markets_from_events` create copies).
7. **Time**: use `datetime.fromtimestamp(ts, tz=timezone.utc)` instead of `utcfromtimestamp`.
8. **SQL compatibility**: all SQL must work on both PostgreSQL and SQLite. No `LIMIT` in `NOT IN` subqueries (PostgreSQL rejects it).
9. **Trade dedup**: use `get_latest_trade_ts()` per market + `latest_ts` parameter in `insert_trade()`. Do NOT add per-row SELECT checks.
10. **News collector**: synchronous (no async/asyncio.run). Uses `httpx.Client` directly.

## Key Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POLYMARKET_PRIVATE_KEY` | (empty) | Ethereum private key for CLOB L2 auth. Enables real trade data with buy/sell sides |
| `POLYMARKET_API_KEY/SECRET/PASSPHRASE` | (empty) | Pre-derived API credentials (skip auto-derivation) |
| `COLLECT_INTERVAL_SEC` | `3600` | Pipeline cycle interval (seconds) |
| `SKIP_ML_FIRST_RUN` | `true` | Skip ML/backtest on first run for faster initial dashboard data |
| `COLLECT_MARKETS_LIMIT` | `0` | Max markets per cycle (0 = all liquid) |
| `MIN_MARKET_VOLUME` | `1000` | Minimum Gamma API volume for a market to be "liquid" |
| `ML_TARGET_HORIZON` | `5` | Predict price up within next N periods |
| `MIN_PRICE_STD` | `0.002` | Skip markets with price std below this |
| `ML_MARKETS_LIMIT` | `20` | Max markets for ML training |
| `FEATURE_MARKETS_LIMIT` | `50` | Max markets for feature computation |
| `BACKTEST_MARKETS_LIMIT` | `15` | Max markets for backtesting |

## Common Tasks

- **Add feature**: `services/feature_store/features.py` → `compute_*`, add to `FEATURE_COLS` in ML module.
- **Change model**: `services/ml_module/models.py` (train_*, walk_forward_validate).
- **Data source**: `services/collector/main.py` (PolymarketClient, CLOB auth via `_init_clob_client`).
- **Risk**: `services/execution_bot/risk.py` (RiskConfig, position_size, should_stop_loss).
- **Add config variable**: `config/settings.py` → `config/__init__.py` → `.env.example`.
- **Add DB migration**: `db/migrations/versions/NNN_description.py` (see existing for pattern).

## Run

```bash
# Web API (FastAPI + Swagger, full pipeline in background)
uvicorn api.app:app --reload --port 8000

# Alternative (same uvicorn, for production)
python server.py

# Individual services
python -m services.collector.main
python -m services.news_collector.main
python -m services.feature_store.main
python -m services.ml_module.main
python -m services.backtester.main
python -m services.execution_bot.main

# Features + ML without collector (for cron, if collector runs separately)
python scripts/run_pipeline.py
```

## Dependencies

- **requirements.txt** — full stack (ML, tests, collector, feature_store, ml_module, py-clob-client). Local and CI.
- Pipeline (features + ml) requires sklearn; for Railway — full requirements.txt (pipeline embedded in web).

## Tests

```bash
python -m pytest tests/ -v
ruff check .
```

- 166 tests total (unit + integration)
- Integration tests use SQLite file-backed DB (conftest.py)
- Backtester stress tests: double fee, high slippage, volatility
- Collector tests: liquidity filter, dedup, orderbook fallback, fee rates
- Pipeline tests: full flow with cleanup patching

## Limitations

- Private keys — only in `.env` / Railway Secrets, never in code.
- Execution Bot: `POLYMARKET_DRY_RUN=true` by default; for real trading need `token_id` (not market_id).
- CLOB `/trades` endpoint requires L2 auth (private key). Without it, falls back to public `prices-history`.
- PMXT: Parquet structure may change — use fallback fields in trades_to_rows / orderbook_to_rows.
- News collector: some RSS feeds may be blocked in certain hosting environments.

## Documentation

- **README.md** — quick start, services, configuration
- **docs/ARCHITECTURE.md** — architecture, tables, features, signals, pipeline
- **docs/RAILWAY.md** — deployment, pipeline, environment variables, troubleshooting
