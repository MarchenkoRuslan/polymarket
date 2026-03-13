# Деплой на Railway

## 1. Проект и база данных

1. Создайте проект в [Railway](https://railway.app)
2. **Add PostgreSQL** — добавит переменную `DATABASE_URL`
3. **Deploy from GitHub** — подключите репозиторий

## 2. Переменные окружения

Добавьте в Settings сервиса:

| Переменная | Значение |
|------------|----------|
| `DATABASE_URL` | Автоматически от PostgreSQL |
| `DATABASE_SSLMODE` | `require` (по умолчанию). Railway PostgreSQL использует SSL |
| `POLYMARKET_CLOB_API` | `https://clob.polymarket.com` |
| `POLYMARKET_GAMMA_API` | `https://gamma-api.polymarket.com` |
| `API_RATE_LIMIT` | `60` |
| `COLLECT_INTERVAL_SEC` | `900` (15 мин), опционально |
| `COLLECT_DEFER_SEC` | `5` — задержка перед первым сбором (сек), чтобы HTTP успел подняться |

## 3. SSL-подключение к PostgreSQL

Railway PostgreSQL автоматически генерирует SSL-сертификаты при инициализации. Приложение подключается с `sslmode=require` по умолчанию.

- **`DATABASE_SSLMODE=require`** — SSL обязателен, сертификат сервера не проверяется (достаточно для Railway)
- **`DATABASE_SSLMODE=disable`** — для локальной разработки без SSL
- Если `DATABASE_URL` уже содержит `?sslmode=...`, значение из URL имеет приоритет

Для локальной разработки с SQLite SSL игнорируется автоматически.

## 4. Инициализация БД

Миграции применяются **автоматически** при старте сервера. Таблицы создадутся при первом запуске, если `DATABASE_URL` настроен.

## 5. Web-сервис + полный pipeline

**Start Command** (в Settings → Deploy):
```bash
uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

Основной сервис — FastAPI (`api.app`):
- `/` и `/health` — health check
- `/docs` — Swagger UI
- `/api/v1/markets`, `/api/v1/trades`, `/api/v1/orderbook`, `/api/v1/signals`, `/api/v1/status` — данные из БД
- **Полный pipeline в фоне**: collector → feature_store → ml_module (при старте и каждые 15 мин)

Интервал: `COLLECT_INTERVAL_SEC=900` (по умолчанию). Для более частого — `600` (10 мин) или `300` (5 мин).

Альтернатива: `python server.py` (тот же uvicorn + pipeline)

## 6. Устранение неполадок

### 502 Bad Gateway

Проверьте:

- **Start Command** — ровно `uvicorn api.app:app --host 0.0.0.0 --port $PORT` (без лишних команд).
- **Порт** — `$PORT` подставляется Railway; без `--host 0.0.0.0` прокси не достучится.
- **Логи** — после строк Alembic ищите traceback или перезапуски контейнера.

Переменная `COLLECT_DEFER_SEC=5` (по умолчанию) откладывает первый сбор на 5 секунд, чтобы HTTP успел подняться до тяжёлых запросов к Polymarket API.

### Логи Alembic как «error»

Сообщения вида `INFO [alembic.runtime.migration] Context impl PostgresqlImpl` Alembic пишет в **stderr**. На Railway stderr часто помечается как `severity: error`, хотя это обычный INFO. Это **не сбой миграций**. Если таблицы созданы — всё в порядке.

### Пустые таблицы

Web-сервис запускает **полный pipeline** (collector → features → ml), поэтому `markets`, `trades`, `orderbook`, `features`, `signals` должны заполняться автоматически.

| Таблица | Источник |
|---------|----------|
| `markets`, `trades`, `orderbook` | Collector (в pipeline) |
| `features`, `signals` | Feature Store + ML Module (в pipeline) |
| `news` | `python -m services.news_collector.main` (отдельно) |
| `orders`, `results` | Execution bot, backtester |

Проверьте `/api/v1/status`: counts, `last_collect_error`, `last_features_error`, `last_ml_error`, `last_pipeline_error`.

## 7. Cron Job (опционально)

Автосбор уже встроен в web-сервис. Отдельный Cron нужен только если хотите полностью отключить фоновый сбор и управлять им через расписание.

Чтобы собирать данные через Cron:

1. **New Service** в том же проекте
2. Выберите **тот же репозиторий** (или подключите заново)
3. **Settings → Cron Schedule**: `*/15 * * * *` (каждые 15 минут, UTC)
4. **Settings → Deploy → Custom Start Command**:
   ```bash
   python -m services.collector.main
   ```
5. Те же переменные окружения (или наследуйте от проекта)
6. Отключите **Public Networking** — cron не должен слушать порт

Сервис запустится по расписанию, выполнит сбор и завершится.

### Расписания

| Расписание | Cron | Описание |
|------------|------|----------|
| Каждые 15 мин | `*/15 * * * *` | ~96 точек/сутки на рынок |
| Каждые 5 мин | `*/5 * * * *` | ~288 точек/сутки |
| Каждые 30 мин | `*/30 * * * *` | ~48 точек/сутки |

За 1–2 дня при `*/15` накопится 100–200 точек на рынок — достаточно для качественных предиктов.

## 8. Дополнительные Cron (опционально)

Pipeline уже встроен в web-сервис. Отдельные Cron нужны только для:

- **Features + ML** (если collector идёт отдельным Cron, а web без pipeline):  
  Start Command `python scripts/run_pipeline.py`, Cron: `0 * * * *`

- **Backtest** (раз в сутки): Start Command `python -m services.backtester.main`  
  Cron: `0 12 * * *`

### Ошибка ML: «only one class in data»

Если в логах: `ValueError: This solver needs samples of at least 2 classes` — данные по рынку содержат только один класс (цены только растут или только падают). ML-модуль пропускает такие рынки. Нужно больше данных: warmup или PMXT.
