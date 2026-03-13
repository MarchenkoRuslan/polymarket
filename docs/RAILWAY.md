# Railway Deployment

## 1. Project and Database

1. Create a project on [Railway](https://railway.app)
2. **Add PostgreSQL** — adds `DATABASE_URL` variable
3. **Deploy from GitHub** — connect your repository

## 2. Environment Variables

Add to service Settings:

<<<<<<< HEAD
| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Auto from PostgreSQL |
=======
| Переменная | Значение |
|------------|----------|
| `DATABASE_URL` | Автоматически от PostgreSQL |
| `DATABASE_SSLMODE` | `require` (рекомендуется для Railway). По умолчанию `prefer` — пробует SSL, fallback без SSL |
>>>>>>> 7660ebffd4e231be81248aaadd85d3d8852f2e8f
| `POLYMARKET_CLOB_API` | `https://clob.polymarket.com` |
| `POLYMARKET_GAMMA_API` | `https://gamma-api.polymarket.com` |
| `API_RATE_LIMIT` | `60` |
| `COLLECT_INTERVAL_SEC` | `900` (15 min), optional |
| `COLLECT_DEFER_SEC` | `5` — delay before first collection (sec), so HTTP is up before heavy Polymarket API calls |

<<<<<<< HEAD
## 3. Database Initialization
=======
## 3. SSL-подключение к PostgreSQL

Railway PostgreSQL автоматически генерирует SSL-сертификаты при инициализации.

- **`DATABASE_SSLMODE=prefer`** (по умолчанию) — пробует SSL, если недоступен — подключается без. Безопасно для локальной разработки и продакшена
- **`DATABASE_SSLMODE=require`** — SSL обязателен, рекомендуется для Railway (добавьте в переменные сервиса)
- **`DATABASE_SSLMODE=disable`** — для локальной разработки без SSL
- Если `DATABASE_URL` уже содержит `?sslmode=...`, значение из URL имеет приоритет

Для локальной разработки с SQLite SSL игнорируется автоматически.

## 4. Инициализация БД
>>>>>>> 7660ebffd4e231be81248aaadd85d3d8852f2e8f

Migrations run **automatically** on server startup. Tables are created on first run when `DATABASE_URL` is set.

<<<<<<< HEAD
## 4. Web Service + Full Pipeline
=======
## 5. Web-сервис + полный pipeline
>>>>>>> 7660ebffd4e231be81248aaadd85d3d8852f2e8f

**Start Command** (in Settings → Deploy):
```bash
uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

Main service — FastAPI (`api.app`):
- `/` and `/health` — health check
- `/docs` — Swagger UI
- `/api/v1/markets`, `/api/v1/trades`, `/api/v1/orderbook`, `/api/v1/signals`, `/api/v1/status` — data from DB
- **Full pipeline in background**: collector → feature_store → ml_module (on startup and every 15 min)

Interval: `COLLECT_INTERVAL_SEC=900` (default). For more frequent — `600` (10 min) or `300` (5 min).

Alternative: `python server.py` (same uvicorn + pipeline)

<<<<<<< HEAD
## 5. Troubleshooting
=======
## 6. Устранение неполадок
>>>>>>> 7660ebffd4e231be81248aaadd85d3d8852f2e8f

### 502 Bad Gateway

Check:

- **Start Command** — exactly `uvicorn api.app:app --host 0.0.0.0 --port $PORT` (no extra commands).
- **Port** — `$PORT` is substituted by Railway; without `--host 0.0.0.0` proxy cannot reach the app.
- **Logs** — after Alembic lines look for traceback or container restarts.

Variable `COLLECT_DEFER_SEC=5` (default) delays first collection by 5 seconds so HTTP is up before heavy Polymarket API requests.

### Alembic Logs as "error"

Messages like `INFO [alembic.runtime.migration] Context impl PostgresqlImpl` Alembic writes to **stderr**. On Railway stderr is often tagged as `severity: error` even though it's normal INFO. This is **not a migration failure**. If tables exist — you're fine.

### Empty Tables

Web service runs the **full pipeline** (collector → features → ml), so `markets`, `trades`, `orderbook`, `features`, `signals` should populate automatically.

| Table | Source |
|-------|--------|
| `markets`, `trades`, `orderbook` | Collector (in pipeline) |
| `features`, `signals` | Feature Store + ML Module (in pipeline) |
| `news` | `python -m services.news_collector.main` (separately) |
| `orders`, `results` | Execution bot, backtester |

Check `/api/v1/status`: counts, `last_collect_error`, `last_features_error`, `last_ml_error`, `last_pipeline_error`.

<<<<<<< HEAD
## 6. Cron Job (optional)
=======
## 7. Cron Job (опционально)
>>>>>>> 7660ebffd4e231be81248aaadd85d3d8852f2e8f

Auto-collection is built into the web service. A separate Cron is only needed if you want to fully disable background collection and control it via schedule.

To collect via Cron:

1. **New Service** in the same project
2. Select **the same repository** (or connect again)
3. **Settings → Cron Schedule**: `*/15 * * * *` (every 15 minutes, UTC)
4. **Settings → Deploy → Custom Start Command**:
   ```bash
   python -m services.collector.main
   ```
5. Same environment variables (or inherit from project)
6. Disable **Public Networking** — cron should not listen on a port

The service will start on schedule, run collection, and exit.

### Schedules

| Schedule | Cron | Description |
|----------|------|-------------|
| Every 15 min | `*/15 * * * *` | ~96 points/day per market |
| Every 5 min | `*/5 * * * *` | ~288 points/day |
| Every 30 min | `*/30 * * * *` | ~48 points/day |

In 1–2 days with `*/15` you get 100–200 points per market — enough for quality predictions.

<<<<<<< HEAD
## 7. Additional Cron Jobs (optional)
=======
## 8. Дополнительные Cron (опционально)
>>>>>>> 7660ebffd4e231be81248aaadd85d3d8852f2e8f

Pipeline is built into the web service. Separate Cron jobs are only for:

- **Features + ML** (if collector runs as separate Cron and web has no pipeline):  
  Start Command `python scripts/run_pipeline.py`, Cron: `0 * * * *`

- **Backtest** (daily): Start Command `python -m services.backtester.main`  
  Cron: `0 12 * * *`

### ML Error: "only one class in data"

If logs show: `ValueError: This solver needs samples of at least 2 classes` — market data has only one class (prices only up or only down). ML module skips such markets. Need more data: warmup or PMXT.
