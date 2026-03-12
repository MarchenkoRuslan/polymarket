"""Tests for FastAPI endpoints."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def client(tmp_path):
    """Client with file-based SQLite so all connections share the same DB."""
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

    # Recreate db.engine with new URL (must do before api import)
    import importlib
    import db
    importlib.reload(db)

    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema_sqlite.sql"
    schema = schema_path.read_text(encoding="utf-8")
    with db.engine.connect() as conn:
        for stmt in schema.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()

    def init_db_mock():
        pass  # schema already applied above

    with patch("api.app.init_db", side_effect=init_db_mock):
        from api.app import app
        return TestClient(app)


def test_root_returns_ok(client):
    """GET / returns 200 OK."""
    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "OK"


def test_health_returns_ok(client):
    """GET /health returns 200 OK."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.text == "OK"


def test_docs_returns_200(client):
    """GET /docs returns 200 (Swagger UI)."""
    r = client.get("/docs")
    assert r.status_code == 200


def test_markets_returns_json(client):
    """GET /api/v1/markets returns JSON with items and total."""
    r = client.get("/api/v1/markets")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)


def test_trades_returns_json(client):
    """GET /api/v1/trades returns JSON with items and total."""
    r = client.get("/api/v1/trades")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


def test_status_returns_json(client):
    """GET /api/v1/status returns JSON with db_ok, markets, trades."""
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    data = r.json()
    assert "db_ok" in data
    assert "markets" in data
    assert "trades" in data
