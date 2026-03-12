"""FastAPI server for Railway: health, API endpoints, background pipeline."""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("server")

_pipeline_status = {
    "last_collect": None,
    "last_features": None,
    "last_ml": None,
    "last_error": None,
    "running": False,
}


def init_db():
    """Run Alembic migrations on startup."""
    try:
        from alembic.config import Config
        from alembic import command

        root = os.path.dirname(os.path.abspath(__file__))
        ini_path = os.path.join(root, "alembic.ini")
        script_location = os.path.join(root, "db", "migrations")

        cfg = Config(ini_path)
        cfg.set_main_option("script_location", script_location)
        url = os.getenv("DATABASE_URL", "")
        if url:
            cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        logger.info("DB migrations applied")
    except Exception:
        logger.exception("DB migration failed")


def _get_status() -> dict:
    """Return status dict: db ok, counts, last_error."""
    out = {"db_ok": False, "markets": 0, "trades": 0, "last_collect_error": _pipeline_status["last_error"]}
    try:
        from db import SessionLocal
        from sqlalchemy import text
        s = SessionLocal()
        try:
            out["markets"] = s.execute(text("SELECT COUNT(*) FROM markets")).scalar() or 0
            out["trades"] = s.execute(text("SELECT COUNT(*) FROM trades")).scalar() or 0
            out["db_ok"] = True
        finally:
            s.close()
    except Exception as e:
        out["db_error"] = str(e)
    return out


async def run_pipeline():
    """Full pipeline: collect → features → ML."""
    if _pipeline_status["running"]:
        logger.info("Pipeline already running, skipping")
        return
    _pipeline_status["running"] = True
    try:
        logger.info("Pipeline: collector starting")
        from services.collector.main import collect_from_api
        await collect_from_api()
        _pipeline_status["last_collect"] = datetime.now(timezone.utc).isoformat()

        logger.info("Pipeline: feature store starting")
        from services.feature_store.main import main as run_features
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_features)
        _pipeline_status["last_features"] = datetime.now(timezone.utc).isoformat()

        logger.info("Pipeline: ML module starting")
        from services.ml_module.main import main as run_ml
        await loop.run_in_executor(None, run_ml)
        _pipeline_status["last_ml"] = datetime.now(timezone.utc).isoformat()

        _pipeline_status["last_error"] = None
        logger.info("Pipeline: complete")
    except Exception as e:
        _pipeline_status["last_error"] = str(e)
        logger.exception("Pipeline error: %s", e)
    finally:
        _pipeline_status["running"] = False


async def pipeline_loop():
    """Background loop: run pipeline on startup, then every N seconds."""
    interval = int(os.environ.get("COLLECT_INTERVAL_SEC", "900"))
    defer = int(os.environ.get("COLLECT_DEFER_SEC", "3"))
    await asyncio.sleep(defer)
    while True:
        await run_pipeline()
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app):
    """Startup: migrate DB, launch background pipeline."""
    init_db()
    task = asyncio.create_task(pipeline_loop())
    logger.info("App ready, listening for requests")
    yield
    task.cancel()


def create_app():
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse, JSONResponse

    app = FastAPI(
        title="Polymarket Trading System",
        description="REST API for Polymarket trading system",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/", include_in_schema=False)
    def root():
        return PlainTextResponse("OK")

    @app.get("/health", include_in_schema=False)
    def health():
        return PlainTextResponse("OK")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        from fastapi.responses import Response
        return Response(status_code=204)

    from api.routes import router
    app.include_router(router)

    @app.get("/pipeline/status")
    def pipeline_status():
        return _pipeline_status

    @app.post("/pipeline/run")
    async def trigger_pipeline():
        if _pipeline_status["running"]:
            return JSONResponse(status_code=409, content={"error": "Pipeline already running"})
        asyncio.create_task(run_pipeline())
        return {"status": "started"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
