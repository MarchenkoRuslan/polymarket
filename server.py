"""Web server for Railway with auto-collect. Health check + background data collection."""
import json
import logging
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)
_last_collect_error = None


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
        command.upgrade(cfg, "head")
        logger.info("DB migrations applied")
    except Exception:
        logger.exception("DB migrations failed")


def run_collect():
    """Run collector in thread (blocking)."""
    global _last_collect_error
    try:
        _last_collect_error = None
        import asyncio
        from services.collector.main import collect_from_api
        asyncio.run(collect_from_api())
    except Exception as e:
        _last_collect_error = str(e)
        logger.exception("Collect error: %s", e)


def collector_loop():
    """Background loop: collect on startup, then every 15 min."""
    interval = int(os.environ.get("COLLECT_INTERVAL_SEC", "900"))  # 15 min
    defer = int(os.environ.get("COLLECT_DEFER_SEC", "5"))
    time.sleep(defer)  # let HTTP server start before heavy API calls
    run_collect()
    while True:
        time.sleep(interval)
        run_collect()


def _get_status():
    """Return status dict: db ok, counts, last_error."""
    out = {"db_ok": False, "markets": 0, "trades": 0, "last_collect_error": _last_collect_error}
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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif self.path == "/status":
            body = json.dumps(_get_status(), indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    t = threading.Thread(target=collector_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
