"""Tests for server.py - init_db, run_collect, run_pipeline, _get_status."""
import asyncio

from unittest.mock import AsyncMock, patch

from server import init_db, run_collect, run_pipeline, _get_status


def test_init_db_does_not_crash():
    """init_db catches errors and sets _migration_error on failure."""
    import server
    init_db()
    assert server._migration_error is None or isinstance(server._migration_error, str)


def test_run_collect_stores_error_and_reraises():
    """run_collect stores error and re-raises so pipeline can react."""
    import server
    with patch(
        "services.collector.main.collect_from_api",
        new_callable=AsyncMock,
        side_effect=ValueError("simulated"),
    ):
        try:
            run_collect()
        except ValueError:
            pass
    assert server._last_collect_error == "simulated"


def test_run_pipeline_calls_collect_news_features_ml_backtest():
    """run_pipeline invokes run_collect, run_news, run_features, run_ml, run_backtest sequentially."""
    with (
        patch("server.run_collect") as mock_c,
        patch("server.run_news") as mock_n,
        patch("server.run_features") as mock_f,
        patch("server.run_ml") as mock_m,
        patch("server.run_backtest") as mock_bt,
    ):
        run_pipeline()
        mock_c.assert_called_once()
        mock_n.assert_called_once()
        mock_f.assert_called_once()
        mock_m.assert_called_once()
        mock_bt.assert_called_once()


def test_run_pipeline_catches_errors():
    """run_pipeline catches exceptions, stores error, does not propagate."""
    import server
    with patch("server.run_collect", side_effect=RuntimeError("boom")):
        run_pipeline()
    assert server._last_pipeline_error == "boom"


def test_run_pipeline_skips_ml_when_features_fail():
    """run_pipeline skips ML and backtest when feature computation fails."""
    with (
        patch("server.run_collect") as mock_c,
        patch("server.run_news") as mock_n,
        patch("server.run_features", side_effect=RuntimeError("features broke")) as mock_f,
        patch("server.run_ml") as mock_m,
        patch("server.run_backtest") as mock_bt,
    ):
        run_pipeline()
        mock_c.assert_called_once()
        mock_n.assert_called_once()
        mock_f.assert_called_once()
        mock_m.assert_not_called()
        mock_bt.assert_not_called()


def test_get_status_returns_dict():
    """_get_status returns dict with all table keys even if DB is unavailable."""
    status = _get_status()
    assert isinstance(status, dict)
    for key in ("db_ok", "markets", "trades", "orderbook", "features",
                "signals", "news", "fee_rates", "orders", "results"):
        assert key in status, f"Missing key: {key}"


def test_skip_lifespan_defaults_false():
    """_skip_lifespan is False by default (uvicorn mode)."""
    import importlib
    import server
    importlib.reload(server)
    assert server._skip_lifespan is False


def test_lifespan_runs_init_when_skip_false():
    """Lifespan calls init_db and pipeline_loop when _skip_lifespan is False."""
    import server
    server._skip_lifespan = False

    with (
        patch("api.app.init_db") as mock_init,
        patch("api.app.pipeline_loop"),
    ):
        from api.app import lifespan
        from fastapi import FastAPI

        async def _run():
            async with lifespan(FastAPI()):
                pass

        asyncio.run(_run())
        mock_init.assert_called_once()


def test_lifespan_skips_init_when_skip_true():
    """Lifespan does NOT call init_db when _skip_lifespan is True."""
    import server
    server._skip_lifespan = True

    with patch("api.app.init_db") as mock_init:
        from api.app import lifespan
        from fastapi import FastAPI

        async def _run():
            async with lifespan(FastAPI()):
                pass

        asyncio.run(_run())
        mock_init.assert_not_called()

    server._skip_lifespan = False
