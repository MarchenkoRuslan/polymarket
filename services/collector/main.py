"""Data Collector - fetches market data from Polymarket API and PMXT."""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import (
    API_RATE_LIMIT,
    POLYMARKET_CLOB_API,
    POLYMARKET_GAMMA_API,
)
from db import SessionLocal
from services.collector.polymarket_client import PolymarketClient
from services.collector.db_writer import (
    upsert_market,
    insert_trade,
    insert_orderbook,
    markets_from_events,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_outcome_prices(raw: str | list | None) -> list[float]:
    """Parse outcomePrices from Gamma API (JSON string or list)."""
    if not raw:
        return []
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return [float(p) for p in raw if p]


def _extract_market_snapshot(m: dict) -> dict | None:
    """Extract price/bid/ask snapshot from Gamma market metadata."""
    prices = _parse_outcome_prices(m.get("outcomePrices"))
    if not prices:
        return None
    price = prices[0]
    if price <= 0 or price >= 1:
        return None
    best_bid = float(m.get("bestBid", 0))
    best_ask = float(m.get("bestAsk", 0))
    if best_bid <= 0:
        best_bid = max(0.01, price - 0.02)
    if best_ask <= 0:
        best_ask = min(0.99, price + 0.02)
    volume = float(m.get("volume", 0) or 0)
    return {
        "price": price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "volume": volume,
    }


async def collect_from_api():
    """Collect markets and sample data from Polymarket API."""
    rate_delay = 60.0 / max(API_RATE_LIMIT, 10) if API_RATE_LIMIT else 0.1
    client = PolymarketClient(POLYMARKET_GAMMA_API, POLYMARKET_CLOB_API, rate_limit_delay=rate_delay)
    session = SessionLocal()
    try:
        events = await client.get_events(active=True, closed=False, limit=20)
        markets = markets_from_events(events)
        snapshots_count = 0

        for m in markets:
            market_id = m.get("id") or m.get("conditionId") or m.get("condition_id")
            if not market_id:
                continue
            if isinstance(market_id, list):
                market_id = market_id[0] if market_id else ""
            market_id = str(market_id)
            upsert_market(session, {**m, "id": market_id})

            snap = _extract_market_snapshot(m)
            if snap:
                now = datetime.now(timezone.utc)
                insert_trade(session, market_id, now, snap["price"], max(snap["volume"], 1.0), "buy")
                insert_orderbook(
                    session, market_id, now,
                    snap["best_bid"], max(snap["volume"] / 2, 1.0),
                    snap["best_ask"], max(snap["volume"] / 2, 1.0),
                )
                snapshots_count += 1

        session.commit()
        logger.info("Upserted %d markets, %d price snapshots from API", len(markets), snapshots_count)

        trades_count = 0
        for m in markets[:5]:
            mid = m.get("id") or m.get("conditionId")
            if isinstance(mid, list):
                mid = mid[0] if mid else ""
            if not mid:
                continue
            mid = str(mid)
            try:
                trades = await client.get_trades(mid, limit=10)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.debug("CLOB trades 401 for %s (auth required), skipping", mid[:16])
                    continue
                raise
            for t in trades:
                ts = t.get("timestamp") or t.get("ts") or t.get("matchTime")
                if isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(
                        ts / 1000 if ts > 1e12 else ts, tz=timezone.utc
                    )
                price = float(t.get("price", 0))
                size = float(t.get("size", t.get("amount", 0)))
                side = str(t.get("side", "BUY")).lower()[:4]
                insert_trade(session, mid, ts, price, size, side)
                trades_count += 1
            session.commit()
        if trades_count:
            logger.info("Inserted %d trades from CLOB API", trades_count)
    except Exception as e:
        session.rollback()
        logger.exception("Collect error: %s", e)
    finally:
        session.close()


async def main():
    """Collector entry point."""
    logger.info("Data Collector starting")
    await collect_from_api()
    logger.info("Data Collector finished")


if __name__ == "__main__":
    asyncio.run(main())
