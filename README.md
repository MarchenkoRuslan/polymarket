# Polymarket Trading System

Автоматизированная система для торговли на прогнозных рынках Polymarket: сбор данных → расчёт фичей → ML-модели → бэктестинг → Execution Bot.

## Требования

- Python 3.11+
- Docker и Docker Compose
- PostgreSQL / TimescaleDB

## Быстрый старт

### Локальный запуск (Docker Compose)

```bash
cp .env.example .env
docker compose up -d db
# Дождаться готовности БД, затем:
docker compose up -d
```

### Локальная разработка

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp .env.example .env
# Запустить PostgreSQL (например docker compose up -d db)
alembic upgrade head
python -m services.collector.main
python -m services.feature_store.main
python -m services.ml_module.main
python -m services.backtester.main
```

## Сервисы

| Сервис | Описание |
|--------|----------|
| `collector` | Сбор данных Polymarket API и PMXT |
| `news_collector` | Сбор новостей (RSS и др.) |
| `feature_store` | Расчёт фичей (MA, volatility, volume) |
| `ml_module` | Обучение моделей (LR, RF) и генерация сигналов |
| `backtester` | Симуляция торговли с комиссиями и проскальзыванием |
| `execution_bot` | Исполнение ордеров (stub) |
| `prometheus` | Метрики |
| `grafana` | Дашборды (порт 3000) |

## Загрузка исторических данных (PMXT)

```bash
python scripts/load_pmxt.py --start 2025-01-01 --days 7
```

## Конфигурация

Переменные окружения (см. `.env.example`):

- `DATABASE_URL` — PostgreSQL
- `POLYMARKET_CLOB_API`, `POLYMARKET_GAMMA_API` — API
- `PMXT_ARCHIVE_URL` — архив PMXT
- `DEFAULT_FEE_BPS` — комиссия (30 = 0.3%)
- `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_PASSPHRASE` — для реальной торговли

## Деплой

1. Настроить `.env` на целевом окружении
2. `docker compose up -d`
3. Запустить миграции: `docker compose run --rm collector alembic upgrade head`
4. При необходимости — загрузка PMXT через `scripts/load_pmxt.py`

## Риски

- Юридические ограничения на ставки (US/CA)
- KYC для Kalshi
- Проверьте правила площадки перед реальной торговлей

## Лицензия

MIT
