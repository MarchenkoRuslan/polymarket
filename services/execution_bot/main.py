"""Execution Bot - places orders via Polymarket API with risk limits."""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text
from db import SessionLocal
from services.execution_bot.risk import RiskConfig, position_size
from services.execution_bot.orders import place_order

try:
    from prometheus_client import Counter, Gauge, start_http_server
    HAS_PROM = True
except ImportError:
    HAS_PROM = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


if HAS_PROM:
    orders_placed = Counter("polymarket_orders_placed_total", "Orders placed")
    orders_rejected = Counter("polymarket_orders_rejected_total", "Orders rejected by risk")
    capital_gauge = Gauge("polymarket_capital", "Current capital")


def run():
    """Check signals, apply risk rules, place orders (dry_run by default)."""
    session = SessionLocal()
    config = RiskConfig()
    capital = 10000.0
    dry_run = os.getenv("POLYMARKET_DRY_RUN", "true").lower() == "true"

    try:
        result = session.execute(
            text("SELECT ts, market_id, prediction FROM signals ORDER BY ts DESC LIMIT 20")
        )
        signals = result.fetchall()
        positions_count = 0
        for ts, market_id, pred in signals:
            if positions_count >= config.max_positions:
                if HAS_PROM:
                    orders_rejected.inc()
                logger.info("Max positions reached, skipping")
                break
            size = position_size(capital, pred, win_loss_ratio=2.0, config=config)
            if size <= 0:
                continue
            # Note: market_id may differ from token_id; real orders need token from Gamma API
            order = place_order(
                token_id=market_id,
                side="buy",
                price=pred,
                size=size,
                dry_run=dry_run,
            )
            if order.get("status") in ("pending", "dry_run", "submitted"):
                positions_count += 1
                if HAS_PROM:
                    orders_placed.inc()
            if HAS_PROM:
                capital_gauge.set(capital)
    except Exception as e:
        logger.exception("%s", e)
    finally:
        session.close()


def main():
    logger.info("Execution Bot starting")
    if HAS_PROM:
        port = _parse_int("PROMETHEUS_PORT", "8000")
        try:
            start_http_server(port)
            logger.info("Prometheus metrics on :%d", port)
        except OSError as e:
            logger.warning("Prometheus metrics server failed (port %d): %s", port, e)
    run()
    logger.info("Execution Bot finished")


if __name__ == "__main__":
    main()
