"""Execution Bot - places orders via Polymarket API with risk limits."""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text
from db import SessionLocal
from services.execution_bot.risk import (
    RiskConfig,
    position_size,
    should_stop_loss,
    should_take_profit,
)
from services.execution_bot.orders import place_order

try:
    from prometheus_client import Counter, Gauge, start_http_server
    HAS_PROM = True
except ImportError:
    HAS_PROM = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EDGE_DISCOUNT = float(os.getenv("EDGE_DISCOUNT_PCT", "0.05"))
BUY_THRESHOLD = 0.5
SELL_THRESHOLD = 0.3


def _parse_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


if HAS_PROM:
    orders_placed = Counter("polymarket_orders_placed_total", "Orders placed")
    orders_rejected = Counter("polymarket_orders_rejected_total", "Orders rejected by risk")
    capital_gauge = Gauge("polymarket_capital", "Current capital")


def _limit_price(prediction: float, side: str) -> float:
    """Apply edge discount so we don't buy at fair value.

    Buy below predicted fair value, sell above.
    """
    if side == "buy":
        return round(prediction * (1 - EDGE_DISCOUNT), 4)
    return round(prediction * (1 + EDGE_DISCOUNT), 4)


def check_open_positions(session, config: RiskConfig, dry_run: bool) -> None:
    """Check open positions for stop-loss / take-profit triggers."""
    result = session.execute(
        text("""
            SELECT o.order_id, o.market_id, o.price AS entry_price, o.size, o.side
            FROM orders o
            WHERE o.status = 'filled'
        """)
    )
    positions = result.fetchall()
    if not positions:
        return

    for order_id, market_id, entry_price, size, side in positions:
        current = session.execute(
            text("SELECT price FROM trades WHERE market_id = :m ORDER BY ts DESC LIMIT 1"),
            {"m": market_id},
        ).fetchone()
        if not current:
            continue
        current_price = float(current[0])
        entry_price = float(entry_price)

        if should_stop_loss(entry_price, current_price, config):
            logger.warning(
                "STOP-LOSS triggered: order=%s market=%s entry=%.4f current=%.4f",
                order_id, market_id[:16], entry_price, current_price,
            )
            close_side = "sell" if side == "buy" else "buy"
            # See NOTE in run(): market_id used as token_id placeholder
            place_order(
                token_id=market_id,
                side=close_side,
                price=_limit_price(current_price, close_side),
                size=float(size),
                dry_run=dry_run,
            )
        elif should_take_profit(entry_price, current_price, config):
            logger.info(
                "TAKE-PROFIT triggered: order=%s market=%s entry=%.4f current=%.4f",
                order_id, market_id[:16], entry_price, current_price,
            )
            close_side = "sell" if side == "buy" else "buy"
            place_order(
                token_id=market_id,
                side=close_side,
                price=_limit_price(current_price, close_side),
                size=float(size),
                dry_run=dry_run,
            )


def run():
    """Check signals, apply risk rules, place orders (dry_run by default)."""
    session = SessionLocal()
    config = RiskConfig()
    capital = 10000.0
    dry_run = os.getenv("POLYMARKET_DRY_RUN", "true").lower() == "true"

    try:
        check_open_positions(session, config, dry_run)

        result = session.execute(
            text(
                "SELECT s.ts, s.market_id, s.prediction FROM signals s "
                "INNER JOIN ("
                "  SELECT market_id, MAX(ts) AS max_ts FROM signals GROUP BY market_id"
                ") latest ON s.market_id = latest.market_id AND s.ts = latest.max_ts "
                "ORDER BY s.ts DESC LIMIT 20"
            )
        )
        signals = result.fetchall()
        positions_count = 0
        for ts, market_id, pred in signals:
            if positions_count >= config.max_positions:
                if HAS_PROM:
                    orders_rejected.inc()
                logger.info("Max positions reached, skipping")
                break

            pred = float(pred)
            if pred < SELL_THRESHOLD:
                side = "sell"
            elif pred >= BUY_THRESHOLD:
                side = "buy"
            else:
                continue

            size = position_size(capital, pred, win_loss_ratio=2.0, config=config)
            if size <= 0:
                continue

            # NOTE: For real orders, token_id (from clobTokenIds) is required,
            # not market_id (conditionId). In dry_run mode market_id is used
            # as a placeholder. For live trading, a market→token mapping
            # must be maintained (e.g. by storing clobTokenIds during collection).
            token_id = market_id

            limit_px = _limit_price(pred, side)
            order = place_order(
                token_id=token_id,
                side=side,
                price=limit_px,
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
        port = _parse_int("PROMETHEUS_PORT", "9100")
        try:
            start_http_server(port)
            logger.info("Prometheus metrics on :%d", port)
        except OSError as e:
            logger.warning("Prometheus metrics server failed (port %d): %s", port, e)
    run()
    logger.info("Execution Bot finished")


if __name__ == "__main__":
    main()
