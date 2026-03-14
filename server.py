"""Web server for Railway. FastAPI + background pipeline (collector → features → ML)."""
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
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
    Falls back to ensuring critical tables exist if migrations fail.
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

    _ensure_news_table_fallback()


def _ensure_news_table_fallback():
    """Ensure the news table exists even if Alembic migration partially failed."""
    try:
        from db import SessionLocal
        from sqlalchemy import text, inspect as sa_inspect
        session = SessionLocal()
        try:
            insp = sa_inspect(session.bind)
            if "news" not in insp.get_table_names():
                dialect = session.bind.dialect.name
                if dialect == "sqlite":
                    session.execute(text(
                        "CREATE TABLE IF NOT EXISTS news ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "ts TEXT NOT NULL, source TEXT NOT NULL, "
                        "title TEXT, link TEXT, summary TEXT, "
                        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
                    ))
                else:
                    session.execute(text(
                        "CREATE TABLE IF NOT EXISTS news ("
                        "id SERIAL PRIMARY KEY, "
                        "ts TIMESTAMP NOT NULL, source TEXT NOT NULL, "
                        "title TEXT, link TEXT, summary TEXT, "
                        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                    ))
                session.execute(text("CREATE INDEX IF NOT EXISTS idx_news_ts ON news (ts)"))
                session.commit()
                logger.info("News table created (fallback)")

            if "markets" in insp.get_table_names():
                cols = [c["name"] for c in insp.get_columns("markets")]
                if "slug" not in cols:
                    session.execute(text("ALTER TABLE markets ADD COLUMN slug TEXT"))
                    session.commit()
                    logger.info("Added slug column to markets (fallback)")
        finally:
            session.close()
    except Exception as e:
        logger.warning("Fallback table check failed: %s", e)


def run_collect():
    """Run collector (blocking). Re-raises on failure so pipeline can react."""
    global _last_collect_error
    with _state_lock:
        _last_collect_error = None
    try:
        import asyncio
        from services.collector.main import collect_from_api
        asyncio.run(collect_from_api())
    except Exception as e:
        with _state_lock:
            _last_collect_error = str(e)
        logger.exception("Collect error: %s", e)
        raise


def run_features():
    """Run Feature Store (blocking). Re-raises on failure."""
    global _last_features_error
    with _state_lock:
        _last_features_error = None
    try:
        from services.feature_store.main import main as fs_main
        fs_main()
    except Exception as e:
        with _state_lock:
            _last_features_error = str(e)
        logger.exception("Feature Store error: %s", e)
        raise


def run_ml():
    """Run ML Module (blocking). Re-raises on failure."""
    global _last_ml_error
    with _state_lock:
        _last_ml_error = None
    try:
        from services.ml_module.main import main as ml_main
        ml_main()
    except Exception as e:
        with _state_lock:
            _last_ml_error = str(e)
        logger.exception("ML Module error: %s", e)
        raise


def run_news():
    """Run News Collector (blocking). Errors are non-fatal for the pipeline."""
    try:
        import asyncio
        from services.news_collector.main import main as news_main
        logger.info("Starting News Collector")
        asyncio.run(news_main())
        logger.info("News Collector completed")
    except Exception as e:
        logger.warning("News Collector error (non-fatal): %s", e, exc_info=True)


def run_backtest():
    """Run Backtester (blocking). Errors are non-fatal for the pipeline."""
    try:
        from services.backtester.main import main as bt_main
        bt_main()
    except Exception as e:
        logger.warning("Backtester error (non-fatal): %s", e)


def run_pipeline():
    """Run full pipeline: collector → news → feature_store → ml_module → backtester."""
    global _last_pipeline_error
    with _state_lock:
        _last_pipeline_error = None
    try:
        run_collect()
    except Exception as e:
        with _state_lock:
            _last_pipeline_error = str(e)
        logger.warning("Pipeline aborted after collect failure")
        return
    run_news()
    try:
        run_features()
    except Exception as e:
        with _state_lock:
            _last_pipeline_error = str(e)
        logger.warning("Pipeline: features failed, skipping ML")
        return
    try:
        run_ml()
    except Exception as e:
        with _state_lock:
            _last_pipeline_error = str(e)
    run_backtest()
    logger.info("Pipeline cycle completed")


def pipeline_loop():
    """Background loop: full pipeline on startup, then every 15 min.

    Applies exponential backoff (up to 1h) on consecutive failures.
    """
    interval = int(os.environ.get("COLLECT_INTERVAL_SEC", "900"))
    defer = int(os.environ.get("COLLECT_DEFER_SEC", "5"))
    max_backoff = 3600
    consecutive_failures = 0
    time.sleep(defer)
    while True:
        try:
            run_pipeline()
            consecutive_failures = 0
        except Exception:
            consecutive_failures += 1
            logger.exception("Pipeline loop error (consecutive: %d)", consecutive_failures)
        if consecutive_failures > 0:
            backoff = min(interval * (2 ** (consecutive_failures - 1)), max_backoff)
            logger.info("Pipeline backoff: %ds (failures: %d)", backoff, consecutive_failures)
            time.sleep(backoff)
        else:
            time.sleep(interval)


def _get_status():
    """Return status dict: db ok, counts, last_error."""
    with _state_lock:
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
