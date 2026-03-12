"""Tests for server.py - init_db, run_collect, run_pipeline, _get_status."""
from unittest.mock import AsyncMock, patch

from server import init_db, run_collect, run_pipeline, _get_status


def test_init_db_does_not_crash():
    """init_db catches errors and does not raise."""
    init_db()


def test_run_collect_catches_errors():
    """run_collect catches exceptions and does not propagate."""
    with patch(
        "services.collector.main.collect_from_api",
        new_callable=AsyncMock,
        side_effect=ValueError("simulated"),
    ):
        run_collect()


def test_run_pipeline_calls_collect_features_ml():
    """run_pipeline invokes run_collect, run_features, run_ml sequentially."""
    with (
        patch("server.run_collect") as mock_c,
        patch("server.run_features") as mock_f,
        patch("server.run_ml") as mock_m,
    ):
        run_pipeline()
        mock_c.assert_called_once()
        mock_f.assert_called_once()
        mock_m.assert_called_once()


def test_run_pipeline_catches_errors():
    """run_pipeline catches exceptions and does not propagate."""
    with patch("server.run_collect", side_effect=RuntimeError("boom")):
        run_pipeline()


def test_get_status_returns_dict():
    """_get_status returns dict with expected keys even if DB is unavailable."""
    status = _get_status()
    assert isinstance(status, dict)
    assert "db_ok" in status
    assert "markets" in status
    assert "trades" in status
