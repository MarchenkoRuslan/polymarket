"""Add slug column to markets table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13

"""
from alembic import op


revision = "002"
down_revision = "001"


def upgrade() -> None:
    op.execute("ALTER TABLE markets ADD COLUMN IF NOT EXISTS slug TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS slug")
