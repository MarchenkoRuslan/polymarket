-- Polymarket Trading System - Database Schema
-- PostgreSQL / TimescaleDB compatible

-- Markets metadata
CREATE TABLE IF NOT EXISTS markets (
    market_id TEXT PRIMARY KEY,
    event TEXT,
    question TEXT,
    end_date TIMESTAMP,
    outcome_settled BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orderbook snapshots (no FK to allow PMXT load before markets)
CREATE TABLE IF NOT EXISTS orderbook (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    market_id TEXT NOT NULL,
    bid_price NUMERIC(10, 6) NOT NULL,
    bid_qty NUMERIC(18, 6) NOT NULL,
    ask_price NUMERIC(10, 6) NOT NULL,
    ask_qty NUMERIC(18, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_orderbook_market_ts ON orderbook (market_id, ts);

-- Trades (no FK to allow PMXT load before markets)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    market_id TEXT NOT NULL,
    price NUMERIC(10, 6) NOT NULL,
    size NUMERIC(18, 6) NOT NULL,
    side VARCHAR(4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_trades_market_ts ON trades (market_id, ts);

-- Fee rates per token
CREATE TABLE IF NOT EXISTS fee_rates (
    token_id TEXT PRIMARY KEY,
    base_fee_bps INTEGER NOT NULL DEFAULT 30,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Features (time-series)
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    market_id TEXT NOT NULL,
    ts TIMESTAMP NOT NULL,
    feature_name TEXT NOT NULL,
    feature_value NUMERIC(18, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_features_market_ts ON features (market_id, ts);

-- Our orders
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    ts_created TIMESTAMP NOT NULL,
    ts_filled TIMESTAMP,
    market_id TEXT NOT NULL,
    side VARCHAR(4) NOT NULL,
    price NUMERIC(10, 6) NOT NULL,
    size NUMERIC(18, 6) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model signals
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    market_id TEXT NOT NULL,
    prediction NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- News (RSS feeds)
CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    source TEXT NOT NULL,
    title TEXT,
    link TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_news_ts ON news (ts);

-- Backtest results
CREATE TABLE IF NOT EXISTS results (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    market_id TEXT NOT NULL,
    profit NUMERIC(18, 6) NOT NULL,
    run_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
