# Polymarket Trading System

Automated system for trading on Polymarket prediction markets: data collection → feature calculation → ML models → backtesting → Execution Bot.

## Requirements

- Python 3.11+
- Docker (optional, for Railway or local PostgreSQL)

## Quick Start

### Web API + data collection (recommended)

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
.\run.ps1 init
.\run.ps1 seed      # or warmup for real data
.\run.ps1 server    # FastAPI + Swagger at http://localhost:8000
```

- **Swagger UI**: http://localhost:8000/docs  
- **API**: `/api/v1/markets`, `/api/v1/trades`, `/api/v1/orderbook`, `/api/v1/signals`, `/api/v1/status`  
- **Full pipeline** in background: collector → features → ML (on startup and every 15 min)

### Full pipeline (without web)

```powershell
.\run.ps1 init
.\run.ps1 seed      # or warmup
.\run.ps1 collect
.\run.ps1 features
.\run.ps1 ml
.\run.ps1 backtest
.\run.ps1 bot
```

Demo data: `.\run.ps1 seed`. Real data: `.\run.ps1 warmup` (~5 min).

### Local run (Docker Compose)

```bash
cp .env.example .env
# In .env set DATABASE_URL=postgresql://polymarket:polymarket@localhost:5432/polymarket
docker compose up -d db
# Wait for DB readiness, then:
docker compose up -d
```

### Local development (PostgreSQL)

```bash
pip install -r requirements.txt
cp .env.example .env
# DATABASE_URL=postgresql://...
alembic upgrade head
python -m services.collector.main
# etc.
```

## Services

| Service | Description |
|---------|-------------|
| **Web API** | FastAPI, Swagger UI. Endpoints: markets, trades, orderbook, signals, status. Full pipeline (collect→features→ml) in background |
| `collector` | Polymarket API data collection (Gamma, CLOB) and PMXT Parquet |
| `news_collector` | RSS news collection with keyword filtering |
| `feature_store` | Features: MA, volatility, RSI, MACD, spread, volume |
| `ml_module` | Model training (LR, RF, XGBoost), signal generation |
| `backtester` | Simulation with fees, slippage, signals 1/0/-1 |
| `execution_bot` | Order placement via py-clob-client (dry-run by default) |
| `prometheus` | Metrics (port 9090) |
| `grafana` | Dashboards (port 3000) |

## Data Loading

### Real data (Polymarket API)

Collector loads:
- **Markets** — from Gamma API (active events)
- **Prices** — from CLOB `prices-history` (if available) or current `lastTradePrice` from Gamma

```powershell
.\run.ps1 collect
```

Run `collect` regularly (e.g. hourly via cron/Task Scheduler) to accumulate history for ML.

### Demo data (no API)

```powershell
.\run.ps1 seed   # 2 markets, 350 trades
```

### PMXT (historical Parquet)

```powershell
.\run.ps1 pmxt --start 2026-03-10 --hours 6
```

- **Hourly format** (default): `polymarket_{trades|orderbook}_{date}T{hour}.parquet`
- **Legacy (daily)**: `.\run.ps1 pmxt --legacy --days 7`
- Options: `--start`, `--hours`, `--url`, `--legacy`, `--days`

## Configuration

Environment variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `POLYMARKET_CLOB_API` | CLOB API URL |
| `POLYMARKET_GAMMA_API` | Gamma API URL |
| `PMXT_ARCHIVE_URL` | PMXT archive URL |
| `DEFAULT_FEE_BPS` | Fee in basis points (30 = 0.3%) |
| `API_RATE_LIMIT` | Requests per minute (for PolymarketClient) |
| `POLYMARKET_DRY_RUN` | `true` (default) — order simulation |
| `POLYMARKET_PRIVATE_KEY` | Private key for real trading |
| `POLYMARKET_PASSPHRASE` | API credentials passphrase |
| `NEWS_KEYWORDS` | Keywords for news filtering (comma-separated) |
| `RSS_FEEDS` | RSS feed URLs (comma-separated) |
| `COLLECT_INTERVAL_SEC` | Background pipeline interval (default 900 = 15 min) |
| `COLLECT_DEFER_SEC` | Delay before first pipeline run (default 5 sec) |

## Testing

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
ruff check .
```

- Unit tests: backtester, features, risk, collector, orders, news, **API** (FastAPI)
- Integration: pipeline collector → features → ml → backtest (SQLite)
- Stress tests: double fee, high slippage, volatility

## Deployment

### Railway

See [docs/RAILWAY.md](docs/RAILWAY.md):

- FastAPI + Swagger, PostgreSQL
- Full pipeline (collector → features → ML) in background
- Cron for collection, Backtest — as needed

### Docker Compose

1. Configure `.env` for target environment
2. `docker compose up -d`
3. Migrations: `docker compose run --rm collector alembic upgrade head`
4. If needed — PMXT load via `scripts/load_pmxt.py`
5. For real trading: `POLYMARKET_DRY_RUN=false`, set `POLYMARKET_PRIVATE_KEY`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Empty `markets`, `trades` | Run `.\run.ps1 seed` or `.\run.ps1 pmxt --hours 6`, then `.\run.ps1 warmup` for real data |
| Empty `features`, `signals` | Pipeline runs after collector. Check `/api/v1/status`: `last_features_error`, `last_ml_error` |
| ML: "only one class in data" | Insufficient price diversity. Add data (PMXT, warmup) |
| `market_id` required | API does not require market_id in request — all query params optional |

## Risks

- Legal restrictions on prediction markets (US/CA)
- KYC for Kalshi
- Check platform rules before real trading
- `market_id` (condition_id) ≠ `token_id` — real orders require token_id from Gamma API

## License

MIT
