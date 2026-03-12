# Polymarket Trading System

Автоматизированная система для торговли на прогнозных рынках Polymarket: сбор данных → расчёт фичей → ML-модели → бэктестинг → Execution Bot.

## Требования

- Python 3.11+
- Docker и Docker Compose (опционально, для PostgreSQL/TimescaleDB)

## Быстрый старт

### Запуск без Docker (SQLite)

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
.\run.ps1 init
.\run.ps1 collect
.\run.ps1 news
.\run.ps1 features
.\run.ps1 ml
.\run.ps1 backtest
.\run.ps1 bot
```

В `.env` по умолчанию `DATABASE_URL=sqlite:///polymarket.db` — локальный файл БД.

### Локальный запуск (Docker Compose)

```bash
cp .env.example .env
# В .env задать DATABASE_URL=postgresql://polymarket:polymarket@localhost:5432/polymarket
docker compose up -d db
# Дождаться готовности БД, затем:
docker compose up -d
```

### Локальная разработка (PostgreSQL)

```bash
pip install -r requirements.txt
cp .env.example .env
# DATABASE_URL=postgresql://...
alembic upgrade head
python -m services.collector.main
# и т.д.
```

## Сервисы

| Сервис | Описание |
|--------|----------|
| `collector` | Сбор данных Polymarket API (Gamma, CLOB) и PMXT Parquet |
| `news_collector` | Сбор RSS-новостей с фильтрацией по ключевым словам |
| `feature_store` | Фичи: MA, volatility, RSI, MACD, spread, volume |
| `ml_module` | Обучение моделей (LR, RF, XGBoost), генерация сигналов |
| `backtester` | Симуляция с комиссиями, проскальзыванием, сигналами 1/0/-1 |
| `execution_bot` | Размещение ордеров через py-clob-client (dry-run по умолчанию) |
| `prometheus` | Метрики (порт 9090) |
| `grafana` | Дашборды (порт 3000) |

## Загрузка данных

### Реальные данные (Polymarket API)

Коллектор загружает:
- **Рынки** — из Gamma API (активные события)
- **Цены** — из CLOB `prices-history` (если доступно) или текущие `lastTradePrice` из Gamma

```powershell
.\run.ps1 collect
```

Запускайте `collect` регулярно (например, раз в час по cron/Task Scheduler), чтобы накопить историю для ML.

### Демо-данные (без API)

```powershell
.\run.ps1 seed   # 2 рынка, 350 сделок
```

### PMXT (исторические Parquet)

```bash
python scripts/load_pmxt.py --start 2025-01-01 --days 7
```

Архив archive.pmxt.dev может быть временно недоступен.

## Конфигурация

Переменные окружения (см. `.env.example`):

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | PostgreSQL connection string |
| `POLYMARKET_CLOB_API` | CLOB API URL |
| `POLYMARKET_GAMMA_API` | Gamma API URL |
| `PMXT_ARCHIVE_URL` | URL архива PMXT |
| `DEFAULT_FEE_BPS` | Комиссия в базисных пунктах (30 = 0.3%) |
| `API_RATE_LIMIT` | Лимит запросов в минуту (для PolymarketClient) |
| `POLYMARKET_DRY_RUN` | `true` (по умолчанию) — симуляция ордеров |
| `POLYMARKET_PRIVATE_KEY` | Приватный ключ для реальной торговли |
| `POLYMARKET_PASSPHRASE` | Пароль для API credentials |
| `NEWS_KEYWORDS` | Ключевые слова для фильтрации новостей (через запятую) |
| `RSS_FEEDS` | URL RSS-лент через запятую |

## Тестирование

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
ruff check .
```

- Unit-тесты: backtester, features, risk, collector, orders, news
- Интеграционные: конвейер collector → features → ml → backtest (SQLite)
- Стресс-тесты: удвоение fee, высокое проскальзывание, волатильность

## Деплой

1. Настроить `.env` на целевом окружении
2. `docker compose up -d`
3. Миграции: `docker compose run --rm collector alembic upgrade head`
4. При необходимости — загрузка PMXT через `scripts/load_pmxt.py`
5. Для реальной торговли: `POLYMARKET_DRY_RUN=false`, задать `POLYMARKET_PRIVATE_KEY`

## Риски

- Юридические ограничения на ставки (US/CA)
- KYC для Kalshi
- Проверьте правила площадки перед реальной торговлей
- `market_id` (condition_id) ≠ `token_id` — для реальных ордеров нужен token_id из Gamma API

## Лицензия

MIT
