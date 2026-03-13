"""Web server for Railway. FastAPI + background pipeline (collector → features → ML)."""
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)
_migration_error = None
_last_collect_error = None
_last_features_error = None
_last_ml_error = None
_last_pipeline_error = None
_skip_lifespan = False

_TABLE_NAMES = ("markets", "trades", "orderbook", "features", "signals", "news", "fee_rates", "orders", "results")


def init_db():
    """Run Alembic migrations on startup.

    Sets _migration_error on failure so /health and /api/v1/status can report it.
    """
    global _migration_error
    try:
        from alembic.config import Config
        from alembic import command

        root = os.path.dirname(os.path.abspath(__file__))
        ini_path = os.path.join(root, "alembic.ini")
        script_location = os.path.join(root, "db", "migrations")

        cfg = Config(ini_path)
        cfg.set_main_option("script_location", script_location)
        command.upgrade(cfg, "head")
        _migration_error = None
        logger.info("DB migrations applied")
    except Exception as e:
        _migration_error = str(e)
        logger.exception("DB migrations failed")


def run_collect():
    """Run collector (blocking). Re-raises on failure so pipeline can react."""
    global _last_collect_error
    try:
        _last_collect_error = None
        import asyncio
        from services.collector.main import collect_from_api
        asyncio.run(collect_from_api())
    except Exception as e:
        _last_collect_error = str(e)
        logger.exception("Collect error: %s", e)
        raise


def run_features():
    """Run Feature Store (blocking). Re-raises on failure."""
    global _last_features_error
    try:
        _last_features_error = None
        from services.feature_store.main import main as fs_main
        fs_main()
    except Exception as e:
        _last_features_error = str(e)
        logger.exception("Feature Store error: %s", e)
        raise


def run_ml():
    """Run ML Module (blocking). Re-raises on failure."""
    global _last_ml_error
    try:
        _last_ml_error = None
        from services.ml_module.main import main as ml_main
        ml_main()
    except Exception as e:
        _last_ml_error = str(e)
        logger.exception("ML Module error: %s", e)
        raise


def run_news():
    """Run News Collector (blocking). Errors are non-fatal for the pipeline."""
    try:
        import asyncio
        from services.news_collector.main import main as news_main
        asyncio.run(news_main())
    except Exception as e:
        logger.warning("News Collector error (non-fatal): %s", e)


def run_pipeline():
    """Run full pipeline: collector → news → feature_store → ml_module."""
    global _last_pipeline_error
    _last_pipeline_error = None
    try:
        run_collect()
    except Exception as e:
        _last_pipeline_error = str(e)
        logger.warning("Pipeline aborted after collect failure")
        return
    run_news()
    try:
        run_features()
    except Exception as e:
        _last_pipeline_error = str(e)
        logger.warning("Pipeline: features failed, skipping ML")
        return
    try:
        run_ml()
    except Exception as e:
        _last_pipeline_error = str(e)
    logger.info("Pipeline cycle completed")


def pipeline_loop():
    """Background loop: full pipeline on startup, then every 15 min."""
    interval = int(os.environ.get("COLLECT_INTERVAL_SEC", "900"))
    defer = int(os.environ.get("COLLECT_DEFER_SEC", "5"))
    time.sleep(defer)
    run_pipeline()
    while True:
        time.sleep(interval)
        run_pipeline()


def _get_status():
    """Return status dict: db ok, counts, last_error."""
    out = {
        "db_ok": False,
        "markets": 0,
        "trades": 0,
        "orderbook": 0,
        "features": 0,
        "signals": 0,
        "migration_error": _migration_error,
        "last_collect_error": _last_collect_error,
        "last_features_error": _last_features_error,
        "last_ml_error": _last_ml_error,
        "last_pipeline_error": _last_pipeline_error,
    }
    try:
        from db import SessionLocal
        from sqlalchemy import text
        s = SessionLocal()
        try:
            for table in _TABLE_NAMES:
                try:
                    out[table] = s.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar() or 0
                except Exception:
                    out[table] = -1
            out["db_ok"] = _migration_error is None
        finally:
            s.close()
    except Exception as e:
        out["db_error"] = str(e)
    return out


def main():
    global _skip_lifespan
    import sys

    # Ensure 'import server' in submodules returns this module, not a second copy.
    # Without this, `python server.py` loads as __main__, and `from server import ...`
    # in api/routes.py creates a separate module with its own globals —
    # pipeline errors would never appear in /api/v1/status.
    sys.modules.setdefault("server", sys.modules[__name__])

    logging.basicConfig(level=logging.INFO)
    init_db()
    t = threading.Thread(target=pipeline_loop, daemon=True)
    t.start()

    _skip_lifespan = True

    port = int(os.environ.get("PORT", 8000))

    import uvicorn
    from api.app import app

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
