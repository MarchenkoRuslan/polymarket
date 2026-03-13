"""Add missing indexes on signals and results tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-13

"""
from alembic import op


revision = "003"
down_revision = "002"


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_signals_market_ts ON signals (market_id, ts)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_results_market_ts ON results (market_id, ts)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_signals_market_ts")
    op.execute("DROP INDEX IF EXISTS idx_results_market_ts")
