# Railway Deployment

## 1. Project and Database

1. Create a project on [Railway](https://railway.app)
2. **Add PostgreSQL** — adds `DATABASE_URL` variable
3. **Deploy from GitHub** — connect your repository

## 2. Environment Variables

Add to service Settings → Variables:

| Variable | Value | Required |
|----------|-------|----------|
| `DATABASE_URL` | Auto from PostgreSQL | auto |
| `DATABASE_SSLMODE` | `require` | recommended |
| `POLYMARKET_CLOB_API` | `https://clob.polymarket.com` | default |
| `POLYMARKET_GAMMA_API` | `https://gamma-api.polymarket.com` | default |
| `POLYMARKET_PRIVATE_KEY` | `0x...` | optional (enables real trade data) |
| `POLYMARKET_API_KEY` | (derived from private key) | optional |
| `POLYMARKET_API_SECRET` | (derived from private key) | optional |
| `POLYMARKET_API_PASSPHRASE` | (derived from private key) | optional |
| `API_RATE_LIMIT` | `60` | optional |
| `COLLECT_INTERVAL_SEC` | `3600` (1 hour) | optional |
| `COLLECT_DEFER_SEC` | `5` | optional |
| `SKIP_ML_FIRST_RUN` | `true` | optional — skip ML/backtest on first run for faster initial dashboard data |
| `MIN_MARKET_VOLUME` | `1000` | optional |
| `ML_TARGET_HORIZON` | `5` | optional |

### CLOB Authentication

For real trade data with proper buy/sell sides:

**Option A**: Set only `POLYMARKET_PRIVATE_KEY` — API credentials are auto-derived on startup.

**Option B**: Set all four: `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_API_KEY`, `POLYMARKET_API_SECRET`, `POLYMARKET_API_PASSPHRASE` — skips derivation, faster startup.

Without auth, the collector uses public `prices-history` API (works fine, but all trades appear as "buy" with size=1).

## 3. Database Initialization

Migrations run **automatically** on server startup via Alembic. Tables and indexes are created on first run.

Current migrations:
- `001` — initial schema (all 9 tables)
- `002` — add slug column to markets
- `003` — add indexes on signals and results
- `004` — add trade deduplication index

## 4. Web Service + Full Pipeline

**Start Command** (in Settings → Deploy):
```bash
python server.py
```

Or:
```bash
uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

Main service — FastAPI (`api.app`):
- `/` and `/health` — health check
- `/docs` — Swagger UI
- `/dashboard` — visual dashboard with 6 tabs (Overview, Trading, Technical, Signals, Performance, News)
- `/api/v1/*` — REST API endpoints

**Background pipeline** (automatic, every hour):
```
cleanup (dedup trades) → collector → news → features → ML → backtest
```

With `SKIP_ML_FIRST_RUN=true` (default), the first run is light: collector + news + features only. Dashboard shows markets, trades, orderbook, features within 2–5 min. ML and backtest run on the next cycle (~1 hour later).

### What populates each table

| Table | Source | When |
|-------|--------|------|
| `markets` | Collector (Gamma API events) | Every pipeline cycle |
| `trades` | Collector (CLOB trades or prices-history) | Every pipeline cycle |
| `orderbook` | Collector (CLOB /book or Gamma bestBid/bestAsk) | Every pipeline cycle |
| `features` | Feature Store (computed from trades) | Every pipeline cycle |
| `signals` | ML Module (trained model predictions) | Every pipeline cycle |
| `news` | News Collector (RSS feeds) | Every pipeline cycle |
| `results` | Backtester (simulated P&L) | Every pipeline cycle |
| `fee_rates` | Collector (per-token fees) | Every pipeline cycle |

## 5. Troubleshooting

### 502 Bad Gateway

Check:

- **Start Command** — use `python server.py` or `uvicorn api.app:app --host 0.0.0.0 --port $PORT`
- **Port** — `$PORT` is substituted by Railway; without `--host 0.0.0.0` proxy cannot reach the app
- `COLLECT_DEFER_SEC=5` (default) delays first collection so HTTP is up before heavy API calls

### Alembic Logs as "error"

Messages like `INFO [alembic.runtime.migration] Context impl PostgresqlImpl` are written to **stderr**. Railway tags stderr as `severity: error`. This is **not a migration failure**. Check `/api/v1/status` → `migration_error` for real errors.

### Empty Tables

Pipeline runs automatically every hour. Check `/api/v1/status`:
- `last_collect_error` — collector issues (API failures, rate limits)
- `last_features_error` — feature computation issues
- `last_ml_error` — ML training issues
- `last_pipeline_error` — general pipeline failure

### All Signals = "sell" (low predictions)

Causes:
- **No CLOB auth**: prices-history returns the same price for each snapshot → no variation → model learns "never goes up"
- **Fix**: Set `POLYMARKET_PRIVATE_KEY` for real trade data with price variation
- **Alternative**: wait for more data accumulation (price variation over hours/days)

### No News

- News collector fetches RSS from Google News, CoinDesk, CoinTelegraph, NY Times
- Some hosting environments may block outgoing HTTP to RSS feeds
- Check logs for "RSS failed" or "timed out" warnings

### ML "single class in data"

Market prices went only up (or only down) in the training period — target has only one class. ML module skips such markets automatically. More data (longer history) helps.

## 6. Monitoring

- `/api/v1/status` — table counts, error messages, DB status
- `/health` — returns 503 if migrations failed
- Dashboard at `/dashboard` — visual overview with auto-refresh

## 7. Cron Job (optional)

Auto-collection is built into the web service. A separate Cron is only needed to fully control the schedule:

1. **New Service** in the same project
2. **Cron Schedule**: `0 * * * *` (every hour, UTC)
3. **Start Command**: `python -m services.collector.main`
4. Same environment variables
5. Disable **Public Networking**

### Pipeline-only Cron (if collector is separate)

Start Command: `python scripts/run_pipeline.py`
Cron: `0 * * * *`
