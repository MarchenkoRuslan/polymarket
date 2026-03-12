"""Web server for Railway with auto-collect. Health check + background data collection."""
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


def run_collect():
    """Run collector in thread (blocking)."""
    try:
        import asyncio
        from services.collector.main import collect_from_api
        asyncio.run(collect_from_api())
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Collect error: %s", e)


def collector_loop():
    """Background loop: collect on startup, then every 15 min."""
    interval = int(os.environ.get("COLLECT_INTERVAL_SEC", "900"))  # 15 min
    run_collect()
    while True:
        time.sleep(interval)
        run_collect()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    t = threading.Thread(target=collector_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
