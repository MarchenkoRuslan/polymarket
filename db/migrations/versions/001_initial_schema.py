"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2025-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            market_id TEXT PRIMARY KEY,
            event TEXT,
            question TEXT,
            end_date TIMESTAMP,
            outcome_settled BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS orderbook (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL,
            market_id TEXT NOT NULL,
            bid_price NUMERIC(10, 6) NOT NULL,
            bid_qty NUMERIC(18, 6) NOT NULL,
            ask_price NUMERIC(10, 6) NOT NULL,
            ask_qty NUMERIC(18, 6) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_market_ts ON orderbook (market_id, ts)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL,
            market_id TEXT NOT NULL,
            price NUMERIC(10, 6) NOT NULL,
            size NUMERIC(18, 6) NOT NULL,
            side VARCHAR(4) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_trades_market_ts ON trades (market_id, ts)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS fee_rates (
            token_id TEXT PRIMARY KEY,
            base_fee_bps INTEGER NOT NULL DEFAULT 30,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id SERIAL PRIMARY KEY,
            market_id TEXT NOT NULL,
            ts TIMESTAMP NOT NULL,
            feature_name TEXT NOT NULL,
            feature_value NUMERIC(18, 8) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_features_market_ts ON features (market_id, ts)")
    op.execute("""
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
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL,
            market_id TEXT NOT NULL,
            prediction NUMERIC(10, 6) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL,
            source TEXT NOT NULL,
            title TEXT,
            link TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_news_ts ON news (ts)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL,
            market_id TEXT NOT NULL,
            profit NUMERIC(18, 6) NOT NULL,
            run_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS results")
    op.execute("DROP TABLE IF EXISTS news")
    op.execute("DROP TABLE IF EXISTS signals")
    op.execute("DROP TABLE IF EXISTS orders")
    op.execute("DROP TABLE IF EXISTS features")
    op.execute("DROP TABLE IF EXISTS fee_rates")
    op.execute("DROP TABLE IF EXISTS trades")
    op.execute("DROP TABLE IF EXISTS orderbook")
    op.execute("DROP TABLE IF EXISTS markets")
