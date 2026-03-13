"""FastAPI application with Swagger UI."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response

from api.routes import router
import server
from server import init_db, pipeline_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, start pipeline thread. Shutdown: cleanup.

    When started via ``python server.py``, init_db and pipeline are already
    running so the flag ``server._skip_lifespan`` is set and we yield
    immediately.  When started via ``uvicorn api.app:app``, the flag is
    ``False`` and we perform full initialization here.
    """
    if not server._skip_lifespan:
        init_db()
        t = threading.Thread(target=pipeline_loop, daemon=True)
        t.start()
    logger.info("App ready, listening for requests")
    yield
    logger.info("App shutting down")


app = FastAPI(
    title="Polymarket API",
    description="REST API for Polymarket trading system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def root():
    """Health check."""
    return PlainTextResponse("OK")


@app.get("/health", include_in_schema=False)
def health():
    """Health check for load balancers. Returns 503 if DB migrations failed."""
    if server._migration_error is not None:
        return PlainTextResponse(
            f"UNHEALTHY: migration failed: {server._migration_error}",
            status_code=503,
        )
    return PlainTextResponse("OK")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """No favicon."""
    return Response(status_code=204)


app.include_router(router)
