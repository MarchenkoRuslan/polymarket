# Polymarket Trading System

Automated system for trading on Polymarket prediction markets: data collection → feature calculation → ML models → backtesting → Execution Bot.

## Requirements

- Python 3.11+
- Docker (optional, for Railway or local PostgreSQL)

## Quick Start

### Web API + data collection (recommended)

```bash
python -m venv venv
source venv/bin/activate    # Linux/macOS
# .\venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
python scripts/init_local.py
python scripts/seed_demo.py     # or warmup for real data
python server.py                # FastAPI + Swagger at http://localhost:8000
```

- **Swagger UI**: http://localhost:8000/docs
- **API**: `/api/v1/markets`, `/api/v1/trades`, `/api/v1/orderbook`, `/api/v1/signals`, `/api/v1/status`, `/api/v1/features`, `/api/v1/news`, `/api/v1/results`, `/api/v1/analytics`
- **UI Dashboard**: separate repo — [polymarket-ui](https://github.com/MarchenkoRuslan/polymarket-ui) (Telegram Web App, connects to this API)
- **Full pipeline** in background: cleanup → collector → news → features → ML → backtest (on startup, then every hour)

### Full pipeline (without web)

```bash
python -m services.collector.main
python -m services.news_collector.main
python -m services.feature_store.main
python -m services.ml_module.main
python -m services.backtester.main
python -m services.execution_bot.main
```

### Local development (Docker Compose)

```bash
cp .env.example .env
# In .env set DATABASE_URL=postgresql://polymarket:polymarket@localhost:5432/polymarket
docker compose up -d db
docker compose up -d
```

## Services

| Service | Description |
|---------|-------------|
| **Web API** | FastAPI, Swagger UI (`/docs`), REST API (`/api/v1/*`). Full pipeline in background (hourly) |
| `collector` | Polymarket API data collection (Gamma markets, CLOB trades with optional L2 auth, orderbook). Filters to liquid markets |
| `news_collector` | RSS news collection (Google News, CoinDesk, CoinTelegraph, NY Times) with keyword filtering |
| `feature_store` | Features: MA, volatility, RSI, MACD, spread, volume. Prioritizes liquid markets |
| `ml_module` | Model training (Logistic Regression, Random Forest, XGBoost), walk-forward validation, signal generation. Multi-period target horizon |
| `backtester` | Simulation with fees (30 bps), slippage (10 bps), signals 1/0/-1 |
| `execution_bot` | Order placement via py-clob-client (dry-run by default) |

## Data Collection

### Real data (Polymarket API)

Collector loads:
- **Markets** — from Gamma API (active events, filtered by liquidity)
- **Trades** — from CLOB API with L2 auth (real buy/sell with sizes) or public `prices-history` (fallback)
- **Orderbook** — from CLOB `/book` or Gamma `bestBid`/`bestAsk`

```bash
python -m services.collector.main
```

### CLOB Authentication (optional, recommended)

For real trade data with proper buy/sell sides and sizes, set up CLOB L2 authentication:

```bash
# Option 1: Private key only (API creds auto-derived on startup)
POLYMARKET_PRIVATE_KEY=0x...your_private_key...

# Option 2: Pre-derived API credentials
POLYMARKET_PRIVATE_KEY=0x...
POLYMARKET_API_KEY=...
POLYMARKET_API_SECRET=...
POLYMARKET_API_PASSPHRASE=...
```

Without auth, the collector uses public `prices-history` API which returns price snapshots without buy/sell distinction.

### Demo data (no API)

```bash
python scripts/seed_demo.py    # 2 markets, 350 trades
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL or SQLite connection string |
| `DATABASE_SSLMODE` | `prefer` | SSL mode for PostgreSQL (`require` for Railway) |
| `POLYMARKET_PRIVATE_KEY` | (empty) | Private key for CLOB L2 auth (enables real trade data) |
| `POLYMARKET_API_KEY/SECRET/PASSPHRASE` | (empty) | Pre-derived CLOB API credentials |
| `COLLECT_INTERVAL_SEC` | `3600` | Pipeline cycle interval (1 hour) |
| `COLLECT_MARKETS_LIMIT` | `0` | Max markets per cycle (0 = all liquid) |
| `MIN_MARKET_VOLUME` | `1000` | Minimum volume to consider a market liquid |
| `ML_TARGET_HORIZON` | `5` | Predict price up within next N periods |
| `MIN_PRICE_STD` | `0.002` | Skip flat-price markets for ML |
| `DEFAULT_FEE_BPS` | `30` | Fee in basis points (0.3%) |
| `API_RATE_LIMIT` | `100` | Polymarket API requests per minute |
| `POLYMARKET_DRY_RUN` | `true` | Order simulation mode |
| `NEWS_KEYWORDS` | `election,crypto,...` | Keywords for news filtering |

## Testing

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
ruff check .
```

- 166 tests total (unit + integration)
- Unit tests: backtester, features, risk, collector, orders, news, API (FastAPI), settings
- Integration: pipeline collector → features → ml → backtest (SQLite)
- Stress tests: double fee, high slippage, volatility

## Deployment

### Railway

See [docs/RAILWAY.md](docs/RAILWAY.md):

- FastAPI + Swagger, PostgreSQL
- Full pipeline in background (hourly): cleanup → collector → news → features → ML → backtest
- Optional: CLOB auth for real trade data

### Docker Compose

1. Configure `.env` for target environment
2. `docker compose up -d`
3. Migrations run automatically on startup
4. For real trading: `POLYMARKET_DRY_RUN=false`, set `POLYMARKET_PRIVATE_KEY`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Empty `markets`, `trades` | Check `/api/v1/status` for errors. Wait for pipeline cycle (1 hour) or run `python -m services.collector.main` |
| Empty `features`, `signals` | Pipeline runs after collector. Check `last_features_error`, `last_ml_error` in `/api/v1/status` |
| All signals = "sell" | Set `POLYMARKET_PRIVATE_KEY` for real trades, or wait for more price history with variation |
| ML: "single class" | Insufficient price diversity. `MIN_PRICE_STD=0.002` filters flat markets. Add more data |
| Empty `news` | News collector runs each pipeline cycle. Check network access to RSS feeds |
| Empty `results` | Backtester runs at end of pipeline. Check that signals exist first |

## License

MIT
