import os
import sys
from logging.config import fileConfig
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy import pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def get_url():
    url = os.getenv("DATABASE_URL", "postgresql://polymarket:polymarket@localhost:5432/polymarket")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    sslmode = os.getenv("DATABASE_SSLMODE", "require")
    if url and url.startswith("postgresql") and sslmode and sslmode != "disable":
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "sslmode" not in qs:
            qs["sslmode"] = [sslmode]
            url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    return url


def _get_connect_args():
    """Return connect_args dict with SSL settings for PostgreSQL."""
    url = get_url()
    sslmode = os.getenv("DATABASE_SSLMODE", "require")
    if url and url.startswith("postgresql") and sslmode and sslmode != "disable":
        return {"sslmode": sslmode}
    return {}


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
        connect_args=_get_connect_args(),
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
