"""Data Collector - fetches market data from Polymarket API and PMXT."""
import asyncio
import json
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


def _parse_outcome_prices(raw) -> list[float]:
    """Parse outcomePrices from Gamma API — handles str, list, None."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            try:
                return [float(x.strip()) for x in raw.split(",") if x.strip()]
            except ValueError:
                return []
    if isinstance(raw, list):
        out = []
        for p in raw:
            try:
                out.append(float(p))
            except (ValueError, TypeError):
                pass
        return out
    try:
        return [float(raw)]
    except (ValueError, TypeError):
        return []


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
        trades_loaded = 0
        for m in markets[:30]:
            mid = m.get("id") or m.get("conditionId") or m.get("condition_id")
            if isinstance(mid, list):
                mid = mid[0] if mid else ""
            if not mid:
                continue
            mid = str(mid)

            asset_id = m.get("clobTokenIds") or []
            if isinstance(asset_id, str):
                try:
                    asset_id = json.loads(asset_id)
                except (json.JSONDecodeError, TypeError):
                    asset_id = []
            if isinstance(asset_id, list) and asset_id:
                asset_id = str(asset_id[0])
            else:
                asset_id = mid

            history = []
            try:
                history = await client.get_prices_history(asset_id, interval="max")
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    logger.debug("prices-history %s for %s, skipping", e.response.status_code, mid[:16])
                else:
                    logger.warning("prices-history error %s: %s", mid[:16], e)
            except Exception:
                pass

            for pt in history:
                ts_raw = pt.get("t") or pt.get("timestamp") or pt.get("ts")
                if ts_raw is None:
                    continue
                if isinstance(ts_raw, (int, float)):
                    ts = datetime.fromtimestamp(
                        ts_raw / 1000 if ts_raw > 1e12 else ts_raw, tz=timezone.utc
                    )
                else:
                    ts = now
                price = float(pt.get("p", pt.get("price", 0)))
                if price <= 0 or price >= 1:
                    continue
                insert_trade(session, mid, ts, price, 1.0, "buy")
                trades_loaded += 1

            if not history:
                prices = _parse_outcome_prices(m.get("outcomePrices"))
                last_trade = m.get("lastTradePrice")
                if last_trade:
                    try:
                        price_val = float(last_trade)
                    except (ValueError, TypeError):
                        price_val = 0
                elif prices:
                    price_val = prices[0]
                else:
                    price_val = 0

                if 0 < price_val < 1:
                    volume = float(m.get("volume", 0) or 0)
                    insert_trade(session, mid, now, price_val, max(volume, 1.0), "buy")
                    trades_loaded += 1

                    best_bid = float(m.get("bestBid", 0) or 0)
                    best_ask = float(m.get("bestAsk", 0) or 0)
                    if best_bid <= 0:
                        best_bid = max(0.01, price_val - 0.02)
                    if best_ask <= 0:
                        best_ask = min(0.99, price_val + 0.02)
                    insert_orderbook(
                        session, mid, now,
                        best_bid, max(volume / 2, 1.0),
                        best_ask, max(volume / 2, 1.0),
                    )

            await asyncio.sleep(0.05)

        if trades_loaded:
            session.commit()
            logger.info("Loaded %d price points from API", trades_loaded)
        else:
            logger.warning("No price data loaded — check API access")
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
