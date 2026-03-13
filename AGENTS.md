# Agent Instructions

Guide for AI agent working with Polymarket Trading System project.

## Project Context

Automated system for trading on Polymarket prediction markets. Full pipeline: data collection (API + PMXT) → news (RSS) → feature calculation → ML models → backtesting → order execution (py-clob-client, dry-run by default).

## Service Structure and Responsibilities

| Service | Path | Task |
|---------|------|------|
| **Web API** | `api/` | FastAPI, Swagger UI (`/docs`). Endpoints: markets, trades, orderbook, signals, status. Lifespan: init_db + pipeline (collector→features→ml) in background |
| Web Server | `server.py` | uvicorn + same FastAPI app. Pipeline in background. For Railway/production |
| Data Collector | `services/collector/` | Polymarket API (Gamma, CLOB), PMXT Parquet → `markets`, `trades`, `orderbook` |
| News Collector | `services/news_collector/` | RSS → keyword filter → `news` table |
| Feature Store | `services/feature_store/` | MA, volatility, RSI, MACD, spread, volume → `features` |
| ML Module | `services/ml_module/` | LR, RF, XGBoost, walk-forward → signals in `signals` |
| Backtester | `services/backtester/` | Simulation with fees, slippage. Signals: 1=buy, 0=hold, -1=sell |
| Execution Bot | `services/execution_bot/` | py-clob-client, risk management (Kelly, limits, stop-loss). Default dry_run |

## Database

- PostgreSQL / SQLite, connection via `DATABASE_URL`
- Schema: `db/schema_sqlite.sql` (local), migrations: `db/migrations/` (Alembic)
- Tables: `markets`, `orderbook`, `trades`, `fee_rates`, `features`, `news`, `signals`, `orders`, `results`

## Code Change Rules

1. **Import paths**: `sys.path.insert(0, project_root)` at entry points. Root — parent of `services/`.
2. **Config**: variables in `config/settings.py`, export in `config/__init__.py`.
3. **Linting**: ruff (`ruff.toml`), Python 3.11.
4. **Backtester**: when changing logic, verify fees (30 bps) and slippage.
5. **ML validation**: walk-forward / TimeSeriesSplit only, no future leakage.
6. **Mutations**: do not mutate input structures (e.g. in `markets_from_events` create copies).
7. **Time**: use `datetime.fromtimestamp(ts, tz=timezone.utc)` instead of `utcfromtimestamp`.

## Common Tasks

- **Add feature**: `services/feature_store/features.py` → `compute_*`, add to `FEATURE_COLS` in ML module.
- **Change model**: `services/ml_module/models.py` (train_*, walk_forward_validate).
- **Data source**: `services/collector/` (PolymarketClient, pmxt_loader).
- **Risk**: `services/execution_bot/risk.py` (RiskConfig, position_size, should_stop_loss).

## Run

```bash
# Web API (FastAPI + Swagger, full pipeline in background)
uvicorn api.app:app --reload --port 8000   # or .\run.ps1 server

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

- **requirements.txt** — full stack (ML, tests, collector, feature_store, ml_module). Local and CI.
- Pipeline (features + ml) requires sklearn; for Railway — full requirements.txt (pipeline embedded in web).

## Tests

```bash
python -m pytest tests/ -v
ruff check .
```

- Integration tests use SQLite in-memory (conftest.py).
- Backtester stress tests: double fee, high slippage, volatility.

## Limitations

- Private keys — only in `.env`, never in code.
- Execution Bot: `POLYMARKET_DRY_RUN=true` by default; for real trading need `token_id` (not market_id).
- PMXT: Parquet structure may change — use fallback fields in trades_to_rows / orderbook_to_rows.

## Documentation

- **README.md** — quick start, services, configuration
- **docs/ARCHITECTURE.md** — architecture, tables, features, signals
- **docs/RAILWAY.md** — deployment, pipeline, 502, Alembic logs, empty tables, ML single-class
