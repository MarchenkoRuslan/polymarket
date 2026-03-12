"""FastAPI application with Swagger UI."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from server import collector_loop, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, start collector thread. Shutdown: none."""
    init_db()
    import threading

    t = threading.Thread(target=collector_loop, daemon=True)
    t.start()
    logger.info("App ready, listening for requests")
    yield


app = FastAPI(
    title="Polymarket API",
    description="REST API for Polymarket trading system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def root():
    """Health check."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("OK")


@app.get("/health", include_in_schema=False)
def health():
    """Health check for load balancers."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("OK")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """No favicon."""
    from fastapi.responses import Response

    return Response(status_code=204)


app.include_router(router)
