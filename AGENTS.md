# Инструкции для агента

Руководство для AI-агента при работе с проектом Polymarket Trading System.

## Контекст проекта

Автоматизированная система для торговли на прогнозных рынках Polymarket. Полный конвейер: сбор данных (API + PMXT) → новости (RSS) → расчёт фичей → ML-модели → бэктестинг → исполнение ордеров (py-clob-client, dry-run по умолчанию).

## Структура и ответственность сервисов

| Сервис | Путь | Задача |
|--------|------|--------|
| **Web API** | `api/` | FastAPI, Swagger UI (`/docs`), эндпоинты `/api/v1/markets`, `/api/v1/trades`, `/api/v1/status`. Lifespan: init_db + collector в фоне |
| Web Server (legacy) | `server.py` | stdlib HTTP, `/`, `/health`, `/status`. Альтернатива без Swagger |
| Data Collector | `services/collector/` | Polymarket API (Gamma, CLOB), PMXT Parquet → `markets`, `trades`, `orderbook` |
| News Collector | `services/news_collector/` | RSS → фильтр по ключевым словам → таблица `news` |
| Feature Store | `services/feature_store/` | MA, volatility, RSI, MACD, spread, volume → `features` |
| ML Module | `services/ml_module/` | LR, RF, XGBoost, walk-forward → сигналы в `signals` |
| Backtester | `services/backtester/` | Симуляция с комиссиями и проскальзыванием. Сигналы: 1=buy, 0=hold, -1=sell |
| Execution Bot | `services/execution_bot/` | py-clob-client, риск-менеджмент (Kelly, лимиты, stop-loss). По умолчанию dry_run |

## База данных

- PostgreSQL / SQLite, подключение через `DATABASE_URL`
- Схема: `db/schema_sqlite.sql` (локально), миграции: `db/migrations/` (Alembic)
- Таблицы: `markets`, `orderbook`, `trades`, `fee_rates`, `features`, `news`, `signals`, `orders`, `results`

## Правила при изменении кода

1. **Пути импорта**: `sys.path.insert(0, project_root)` в точках входа. Корень — родитель `services/`.
2. **Конфиг**: переменные в `config/settings.py`, экспорт в `config/__init__.py`.
3. **Линтинг**: ruff (`ruff.toml`), Python 3.11.
4. **Бэктестер**: при изменении логики проверять комиссии (30 bps) и проскальзывание.
5. **Валидация ML**: только walk-forward / TimeSeriesSplit, без утечки будущего.
6. **Мутации**: не мутировать входные структуры (например, в `markets_from_events` создавать копии).
7. **Время**: использовать `datetime.fromtimestamp(ts, tz=timezone.utc)` вместо `utcfromtimestamp`.

## Частые задачи

- **Добавить фичу**: `services/feature_store/features.py` → `compute_*`, добавить в `FEATURE_COLS` в ML-модуле.
- **Изменить модель**: `services/ml_module/models.py` (train_*, walk_forward_validate).
- **Источник данных**: `services/collector/` (PolymarketClient, pmxt_loader).
- **Риск**: `services/execution_bot/risk.py` (RiskConfig, position_size, should_stop_loss).

## Запуск

```bash
# Web API (FastAPI + Swagger, collector в фоне)
uvicorn api.app:app --reload --port 8000   # или .\run.ps1 server

# Альтернатива (stdlib HTTP)
python server.py

# Отдельные сервисы
python -m services.collector.main
python -m services.news_collector.main
python -m services.feature_store.main
python -m services.ml_module.main
python -m services.backtester.main
python -m services.execution_bot.main
```

## Зависимости

- **requirements-web.txt** — для Docker/Railway (web + collector). Без sklearn, xgboost, pyarrow, pytest. Быстрый билд.
- **requirements.txt** — полный стек (ML, тесты). Локально и CI.

## Тесты

```bash
python -m pytest tests/ -v
ruff check .
```

- Интеграционные тесты используют SQLite in-memory (conftest.py).
- Стресс-тесты бэктестера: double fee, high slippage, volatility.

## Ограничения

- Приватные ключи — только в `.env`, не в коде.
- Execution Bot: `POLYMARKET_DRY_RUN=true` по умолчанию; для реальной торговли нужен `token_id` (не market_id).
- PMXT: структура Parquet может меняться — использовать fallback-поля в trades_to_rows / orderbook_to_rows.

## Документация

- **README.md** — быстрый старт, сервисы, конфигурация
- **docs/ARCHITECTURE.md** — архитектура, таблицы, фичи, сигналы
- **docs/RAILWAY.md** — деплой, 502, логи Alembic, пустые таблицы, requirements-web
