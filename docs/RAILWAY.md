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
| `POLYMARKET_CLOB_API` | `https://clob.polymarket.com` |
| `POLYMARKET_GAMMA_API` | `https://gamma-api.polymarket.com` |
| `API_RATE_LIMIT` | `60` |
| `COLLECT_INTERVAL_SEC` | `900` (15 мин), опционально |

## 3. Инициализация БД

Миграции применяются **автоматически** при старте сервера. Таблицы создадутся при первом запуске, если `DATABASE_URL` настроен.

## 4. Web-сервис + автосбор

**Start Command** (в Settings → Deploy):
```bash
uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

Основной сервис — FastAPI (`api.app`):
- `/` и `/health` — health check
- `/docs` — Swagger UI
- `/api/v1/markets`, `/api/v1/trades`, `/api/v1/status` — данные из БД
- **Автоматически собирает данные** в фоне: при старте и каждые 15 мин

Интервал: `COLLECT_INTERVAL_SEC=900` (по умолчанию). Для более частого сбора задайте `600` (10 мин) или `300` (5 мин).

Альтернатива (без Swagger): `python server.py`

## 5. Cron Job (опционально)

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

## 6. Дополнительные Cron (опционально)

Можно добавить отдельные сервисы для:

- **Features + ML** (раз в час): Start Command `python scripts/run_pipeline.py`  
  Cron: `0 * * * *`

- **Backtest** (раз в сутки): Start Command `python -m services.backtester.main`  
  Cron: `0 12 * * *`

Убедитесь, что collector запускается чаще, чем features/ml.
