"""Tests for server.py - health check, init_db, run_collect."""
import json
import threading
import urllib.request
from unittest.mock import AsyncMock, patch

import pytest

from server import Handler, init_db, run_collect


def test_handler_root_returns_ok():
    """GET / returns 200 OK."""
    from http.server import HTTPServer

    server = HTTPServer(("", 0), Handler)
    port = server.server_address[1]

    def serve_one():
        server.handle_request()

    t = threading.Thread(target=serve_one)
    t.start()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
        assert r.status == 200
        assert r.read() == b"OK"
    t.join()


def test_handler_health_returns_ok():
    """GET /health returns 200 OK."""
    from http.server import HTTPServer

    server = HTTPServer(("", 0), Handler)
    port = server.server_address[1]

    def serve_one():
        server.handle_request()

    t = threading.Thread(target=serve_one)
    t.start()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
        assert r.status == 200
        assert r.read() == b"OK"
    t.join()


def test_handler_favicon_returns_204():
    """GET /favicon.ico returns 204 No Content."""
    from http.server import HTTPServer

    server = HTTPServer(("", 0), Handler)
    port = server.server_address[1]

    def serve_one():
        server.handle_request()

    t = threading.Thread(target=serve_one)
    t.start()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/favicon.ico")
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 204
    t.join()


def test_handler_status_returns_json():
    """GET /status returns 200 and JSON with db_ok, markets, trades."""
    from http.server import HTTPServer

    server = HTTPServer(("", 0), Handler)
    port = server.server_address[1]

    def serve_one():
        server.handle_request()

    t = threading.Thread(target=serve_one)
    t.start()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert "db_ok" in data
        assert "markets" in data
        assert "trades" in data
    t.join()


def test_handler_unknown_returns_404():
    """GET /unknown returns 404."""
    from http.server import HTTPServer

    server = HTTPServer(("", 0), Handler)
    port = server.server_address[1]

    def serve_one():
        server.handle_request()

    t = threading.Thread(target=serve_one)
    t.start()
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/unknown", timeout=2)
    assert exc_info.value.code == 404
    t.join()


def test_init_db_does_not_crash():
    """init_db catches errors and does not raise."""
    init_db()


def test_run_collect_catches_errors():
    """run_collect catches exceptions and does not propagate."""
    with patch("services.collector.main.collect_from_api", new_callable=AsyncMock, side_effect=ValueError("simulated")):
        run_collect()
