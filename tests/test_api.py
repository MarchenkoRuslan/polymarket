"""Tests for FastAPI API endpoints."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client with file-based SQLite for isolated API tests."""
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)
    import config as config_mod
    importlib.reload(config_mod)
    import db as db_mod
    importlib.reload(db_mod)

    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema_sqlite.sql"
    schema = schema_path.read_text(encoding="utf-8")
    with db_mod.engine.connect() as conn:
        for stmt in schema.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()

    import server as server_mod
    importlib.reload(server_mod)
    import api.routes as routes_mod
    importlib.reload(routes_mod)

    app = server_mod.create_app()
    return TestClient(app, raise_server_exceptions=False)


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
