"""Add index for trade deduplication (market_id, ts, price).

Revision ID: 004
Revises: 003
Create Date: 2026-03-14

"""
from alembic import op


revision = "004"
down_revision = "003"


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_trades_dedup "
        "ON trades (market_id, ts, price)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_trades_dedup")
