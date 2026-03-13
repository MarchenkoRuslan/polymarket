"""Pytest fixtures for integration tests."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema_sqlite.sql"


@pytest.fixture(scope="function")
def sqlite_db(tmp_path, monkeypatch):
    """Create a file-backed SQLite DB with schema for integration tests."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_SSLMODE", "disable")
    engine = create_engine(db_url)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.connect() as conn:
        for stmt in schema.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, Session
