"""Data Collector - fetches market data from Polymarket API and PMXT."""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    markets_from_events,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def collect_from_api():
    """Collect markets and sample data from Polymarket API."""
    rate_delay = 60.0 / max(API_RATE_LIMIT, 10) if API_RATE_LIMIT else 0.1
    client = PolymarketClient(POLYMARKET_GAMMA_API, POLYMARKET_CLOB_API, rate_limit_delay=rate_delay)
    session = SessionLocal()
    try:
        events = await client.get_events(active=True, closed=False, limit=50)
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

        now = datetime.now(timezone.utc)
        loaded = 0
        for m in markets[:30]:
            mid = m.get("id") or m.get("conditionId") or m.get("condition_id")
            if isinstance(mid, list):
                mid = mid[0] if mid else ""
            if not mid:
                continue
            mid = str(mid)
            asset_id = m.get("clobTokenIds") or []
            if isinstance(asset_id, list) and asset_id:
                asset_id = str(asset_id[0])
            else:
                asset_id = mid
            history = []
            try:
                history = await client.get_prices_history(asset_id, interval="max")
            except Exception:
                pass
            for pt in history:
                ts_raw = pt.get("t") or pt.get("timestamp") or pt.get("ts")
                if ts_raw is None:
                    continue
                ts = datetime.fromtimestamp(
                    ts_raw / 1000 if ts_raw > 1e12 else ts_raw, tz=timezone.utc
                )
                price = float(pt.get("p", pt.get("price", 0)))
                if price <= 0 or price >= 1:
                    continue
                insert_trade(session, mid, ts, price, 1.0, "buy")
                loaded += 1
            if not history:
                price_val = m.get("lastTradePrice") or (m.get("outcomePrices") or "0.5")
                if isinstance(price_val, str):
                    try:
                        price_val = float(price_val.split(",")[0].strip())
                    except (ValueError, IndexError):
                        price_val = 0.5
                price_val = float(price_val)
                if 0 < price_val < 1:
                    insert_trade(session, mid, now, price_val, 1.0, "buy")
                    loaded += 1
            await asyncio.sleep(0.1)
        if loaded:
            session.commit()
            logger.info("Loaded %d price points from API", loaded)
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
