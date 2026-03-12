# Инструкции для агента

Руководство для AI-агента при работе с проектом Polymarket Trading System.

## Контекст проекта

Автоматизированная система для торговли на прогнозных рынках Polymarket. Полный конвейер: сбор данных → расчёт фичей → ML-модели → бэктестинг → исполнение ордеров.

## Структура и ответственность сервисов

| Сервис | Путь | Задача |
|--------|------|--------|
| Data Collector | `services/collector/` | Polymarket API, PMXT Parquet, запись в `markets`, `trades`, `orderbook` |
| News Collector | `services/news_collector/` | RSS/новости для внешних сигналов |
| Feature Store | `services/feature_store/` | Фичи MA, volatility, volume → таблица `features` |
| ML Module | `services/ml_module/` | Обучение моделей (LR, RF, XGBoost), генерация сигналов в `signals` |
| Backtester | `services/backtester/` | Симуляция с комиссиями и проскальзыванием |
| Execution Bot | `services/execution_bot/` | Размещение ордеров, риск-менеджмент (Kelly, лимиты, stop-loss) |

## База данных

- PostgreSQL / TimescaleDB, подключение через `DATABASE_URL`
- Схема в `db/schema.sql`, миграции Alembic в `db/migrations/`
- Таблицы: `markets`, `orderbook`, `trades`, `fee_rates`, `features`, `orders`, `signals`, `results`

## Правила при изменении кода

1. **Пути импорта**: используется `sys.path.insert(0, project_root)` в точках входа. Корень проекта — родитель `services/`.
2. **Конфиг**: переменные окружения читаются через `config/settings.py` и `config/__init__.py`.
3. **Линтинг**: ruff (см. `ruff.toml`), target Python 3.11.
4. **Бэктестер**: при любых изменениях логики исполнения ордеров проверять корректность учёта комиссий (30 bps) и проскальзывания.
5. **Валидация ML**: использовать только walk-forward / TimeSeriesSplit, не допускать утечки будущего в обучение.

## Частые задачи

- **Добавить фичу**: `services/feature_store/features.py` → `compute_*`, `FEATURE_COLS` в ML-модуле.
- **Изменить модель**: `services/ml_module/models.py`, добавить в `train_*` и `walk_forward_validate`.
- **Добавить источник данных**: `services/collector/` (PolymarketClient или pmxt_loader).
- **Настроить риск**: `services/execution_bot/risk.py` → `RiskConfig`, `position_size`.

## Запуск

```bash
# Docker
docker compose up -d db && docker compose up -d

# Локально (после pip install -r requirements.txt)
python -m services.collector.main
python -m services.feature_store.main
python -m services.ml_module.main
python -m services.backtester.main
```

## Ограничения

- Не хранить приватные ключи в коде. Использовать `.env` и переменные окружения.
- Execution Bot по умолчанию — stub: ордера не отправляются на биржу.
- При работе с PMXT: структура Parquet может меняться, обрабатывать разные названия колонок.

## Документация

- Архитектура: `docs/ARCHITECTURE.md`
- План: `c:\Users\Руслан\.cursor\plans\polymarket_trading_system_da9cbd85.plan.md`
- Спецификация: `c:\Users\Руслан\Desktop\Полимаркет.pdf`
