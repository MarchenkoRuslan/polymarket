# Инструкции для агента

Руководство для AI-агента при работе с проектом Polymarket Trading System.

## Контекст проекта

Автоматизированная система для торговли на прогнозных рынках Polymarket. Полный конвейер: сбор данных (API + PMXT) → новости (RSS) → расчёт фичей → ML-модели → бэктестинг → исполнение ордеров (py-clob-client, dry-run по умолчанию).

## Структура и ответственность сервисов

| Сервис | Путь | Задача |
|--------|------|--------|
| Data Collector | `services/collector/` | Polymarket API (Gamma, CLOB), PMXT Parquet → `markets`, `trades`, `orderbook` |
| News Collector | `services/news_collector/` | RSS → фильтр по ключевым словам → таблица `news` |
| Feature Store | `services/feature_store/` | MA, volatility, RSI, MACD, spread, volume → `features` |
| ML Module | `services/ml_module/` | LR, RF, XGBoost, walk-forward → сигналы в `signals` |
| Backtester | `services/backtester/` | Симуляция с комиссиями и проскальзыванием. Сигналы: 1=buy, 0=hold, -1=sell |
| Execution Bot | `services/execution_bot/` | py-clob-client, риск-менеджмент (Kelly, лимиты, stop-loss). По умолчанию dry_run |

## База данных

- PostgreSQL / TimescaleDB, подключение через `DATABASE_URL`
- Схема: `db/schema.sql`, миграции: `db/migrations/`
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
# Docker
docker compose up -d db && docker compose up -d

# Локально
python -m services.collector.main
python -m services.news_collector.main
python -m services.feature_store.main
python -m services.ml_module.main
python -m services.backtester.main
python -m services.execution_bot.main
```

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

- Архитектура: `docs/ARCHITECTURE.md`
- README: `README.md`
