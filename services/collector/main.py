"""Data Collector - fetches market data from Polymarket API and PMXT."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import (
    POLYMARKET_CLOB_API,
    POLYMARKET_GAMMA_API,
)
from db import SessionLocal
from services.collector.polymarket_client import PolymarketClient
from services.collector.db_writer import (
    upsert_market,
    insert_trade,
    markets_from_events,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def collect_from_api():
    """Collect markets and sample data from Polymarket API."""
    client = PolymarketClient(POLYMARKET_GAMMA_API, POLYMARKET_CLOB_API)
    session = SessionLocal()
    try:
        events = await client.get_events(active=True, closed=False, limit=20)
        markets = markets_from_events(events)
        for m in markets:
            market_id = m.get("id") or m.get("conditionId") or m.get("condition_id")
            if not market_id:
                continue
            if isinstance(market_id, list):
                market_id = market_id[0] if market_id else ""
            market_id = str(market_id)
            upsert_market(session, {**m, "id": market_id})

        session.commit()
        logger.info("Upserted %d markets from API", len(markets))

        for m in markets[:3]:
            mid = m.get("id") or m.get("conditionId")
            if isinstance(mid, list):
                mid = mid[0] if mid else ""
            if not mid:
                continue
            mid = str(mid)
            trades = await client.get_trades(mid, limit=10)
            for t in trades:
                ts = t.get("timestamp") or t.get("ts") or t.get("matchTime")
                if isinstance(ts, (int, float)):
                    from datetime import datetime
                    ts = datetime.utcfromtimestamp(ts / 1000 if ts > 1e12 else ts)
                price = float(t.get("price", 0))
                size = float(t.get("size", t.get("amount", 0)))
                side = str(t.get("side", "BUY")).lower()[:4]
                insert_trade(session, mid, ts, price, size, side)
                await asyncio.sleep(0.05)
            session.commit()
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
