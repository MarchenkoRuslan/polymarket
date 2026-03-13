# Архитектура системы

```
┌─────────────────┐   ┌─────────────────┐
│ Data Collector  │   │ News Collector  │
│ (API + PMXT)    │   │ (RSS)           │
└────────┬────────┘   └────────┬────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │   PostgreSQL /      │
         │   SQLite            │
         └──────────┬──────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│  Web API    │  │ Feature     │  │   ML Module     │
│  FastAPI    │  │ Store       │  │ (LR, RF, XGB)   │
│  Swagger    │  │ (MA, RSI)   │  └────────┬────────┘
│  /api/v1/*  │  └──────┬──────┘           │
└─────────────┘         └──────────┬───────┘
                                   ▼
                        ┌─────────────────────┐
                        │    Backtester       │
                        │    Execution Bot    │
                        └──────────┬──────────┘
                                   ▼
                        ┌─────────────────────┐
                        │  Polymarket CLOB    │
                        │  (py-clob-client)   │
                        └─────────────────────┘
```

Web API (FastAPI, `/docs`) читает данные из БД и запускает **полный pipeline** в фоне: collector → feature_store → ml_module.

### Эндпоинты API

| Путь | Описание |
|------|----------|
| `GET /docs` | Swagger UI |
| `GET /api/v1/markets` | Список рынков (limit, offset) |
| `GET /api/v1/markets/{market_id}` | Один рынок |
| `GET /api/v1/trades` | Сделки (market_id опционально, limit, offset) |
| `GET /api/v1/orderbook` | Снимки стакана (market_id опционально, limit, offset) |
| `GET /api/v1/signals` | ML-сигналы (market_id опционально, limit, offset) |
| `GET /api/v1/status` | db_ok, counts (markets, trades, orderbook, features, signals), last_*_error |

## Таблицы БД

| Таблица | Описание |
|---------|----------|
| `markets` | Метаданные рынков (question, end_date, outcome_settled) |
| `orderbook` | Снимки стакана (bid/ask, qty) |
| `trades` | Сделки (price, size, side) |
| `fee_rates` | Комиссии по токенам |
| `features` | Рассчитанные фичи (market_id, ts, feature_name, value) |
| `news` | Новости из RSS (title, link, summary) |
| `signals` | Сигналы модели (prediction) |
| `orders` | Наши ордера |
| `results` | Результаты бэктеста |

Индексы: `(market_id, ts)` на orderbook, trades, features.

## Фичи

- **Ценовые**: ma_1h, ma_5m, volatility_1h, roc_1h, rsi_14, macd, macd_signal, macd_hist
- **Объёмные**: volume_1h, volume_5m
- **Ликвидность**: spread, spread_bps (при наличии bid/ask)

## Сигналы бэктестера

- `1` — buy (prediction ≥ 0.5)
- `0` — hold (0.3 ≤ prediction < 0.5)
- `-1` — sell (prediction < 0.3)

## Валидация модели

- TimeSeriesSplit / walk-forward
- Запрет утечки: train до t, test на t+1..t+k
- Если в target только один класс (все цены идут вниз/вверх) — рынок пропускается: `single class in target, skipping`

## Execution Bot

- По умолчанию: `POLYMARKET_DRY_RUN=true` — ордера не отправляются
- Реальная торговля: `POLYMARKET_DRY_RUN=false`, задать `POLYMARKET_PRIVATE_KEY`
- `market_id` (condition_id) ≠ `token_id` — для ордеров через CLOB нужен token_id
