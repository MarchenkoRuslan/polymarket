"""Add slug column to markets table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect


revision = "002"
down_revision = "001"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    columns = [c["name"] for c in insp.get_columns("markets")]
    if "slug" not in columns:
        op.add_column("markets", sa.Column("slug", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "sqlite":
        op.drop_column("markets", "slug")
