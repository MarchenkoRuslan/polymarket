"""FastAPI application with Swagger UI."""
import logging
import os
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from api.routes import router
import server
from server import init_db, pipeline_loop

logger = logging.getLogger(__name__)

_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "*").split(",")
    if o.strip()
]

_RATE_LIMIT_RPM = int(os.getenv("API_RATE_LIMIT_RPM", "120"))
_rate_store: dict[str, list[float]] = defaultdict(list)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple in-memory sliding-window rate limiter per client IP."""
    if _RATE_LIMIT_RPM <= 0 or not request.url.path.startswith("/api/"):
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = 60.0
    timestamps = _rate_store[client_ip]
    timestamps[:] = [t for t in timestamps if now - t < window]
    if len(timestamps) >= _RATE_LIMIT_RPM:
        return JSONResponse(
            {"detail": "Rate limit exceeded. Try again later."},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    timestamps.append(now)
    return await call_next(request)


@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    """Add Cache-Control and ETag headers to API responses."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return response


app.include_router(router)
