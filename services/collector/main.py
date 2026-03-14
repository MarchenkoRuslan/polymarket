"""Data Collector - fetches market data from Polymarket API and PMXT."""
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import (
    API_RATE_LIMIT,
    COLLECT_MARKETS_LIMIT,
    DEFAULT_FEE_BPS,
    POLYMARKET_CLOB_API,
    POLYMARKET_GAMMA_API,
)
from db import SessionLocal
from services.collector.polymarket_client import PolymarketClient
from sqlalchemy import text as sa_text
from services.collector.db_writer import (
    upsert_market,
    insert_trade,
    insert_orderbook,
    upsert_fee_rate,
    markets_from_events,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_outcome_prices(raw) -> float | None:
    """Parse outcomePrices from Gamma API.

    Handles: str ("0.55"), JSON string ('["0.145","0.855"]'),
    list (["0.145", "0.855"]), float, int, None.
    Returns the first outcome price as float, or None if unparseable.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        return val if 0 < val < 1 else None
    if isinstance(raw, list):
        for item in raw:
            try:
                val = float(item)
                if 0 < val < 1:
                    return val
            except (TypeError, ValueError):
                continue
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                return _parse_outcome_prices(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        for part in raw.split(","):
            try:
                val = float(part.strip().strip('"').strip("'"))
                if 0 < val < 1:
                    return val
            except (ValueError, TypeError):
                continue
    return None


def _parse_clob_token_ids(raw) -> list[str]:
    """Parse clobTokenIds which can be a JSON string, list, or None."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x]
            except (json.JSONDecodeError, TypeError):
                pass
        if raw:
            return [raw]
    return []


def _extract_market_id(market: dict) -> str:
    """Extract market_id from a market dict with fallbacks."""
    mid = market.get("id") or market.get("conditionId") or market.get("condition_id")
    if not mid:
        return ""
    if isinstance(mid, list):
        mid = mid[0] if mid else ""
    return str(mid)


async def _collect_orderbook(
    client: PolymarketClient,
    session,
    market: dict,
    market_id: str,
    token_id: str,
    now: datetime,
) -> bool:
    """Fetch orderbook: try CLOB get_orderbook() first, fallback to Gamma bestBid/bestAsk.

    Returns True if an orderbook snapshot was inserted.
    """
    bid_p: float | None = None
    ask_p: float | None = None
    bid_q: float = 1.0
    ask_q: float = 1.0

    try:
        book = await client.get_orderbook(token_id)
        if book:
            bids = book.get("bids") or []
            asks = book.get("asks") or []
            if bids and asks:
                best_bid_entry = bids[0] if isinstance(bids[0], dict) else {"price": bids[0]}
                best_ask_entry = asks[0] if isinstance(asks[0], dict) else {"price": asks[0]}
                bp = float(best_bid_entry.get("price", 0))
                ap = float(best_ask_entry.get("price", 0))
                bq = float(best_bid_entry.get("size", best_bid_entry.get("qty", 1.0)))
                aq = float(best_ask_entry.get("size", best_ask_entry.get("qty", 1.0)))
                if 0 < bp < 1 and 0 < ap < 1:
                    bid_p, ask_p = bp, ap
                    bid_q, ask_q = bq, aq
    except Exception as e:
        logger.debug("CLOB orderbook for %s unavailable: %s", market_id, e)

    if bid_p is None or ask_p is None:
        raw_bid = market.get("bestBid")
        raw_ask = market.get("bestAsk")
        if raw_bid is not None and raw_ask is not None:
            try:
                bp = float(raw_bid)
                ap = float(raw_ask)
                if 0 < bp < 1 and 0 < ap < 1:
                    bid_p, ask_p = bp, ap
                    bid_q, ask_q = 1.0, 1.0
            except (TypeError, ValueError):
                pass

    if bid_p is not None and ask_p is not None:
        insert_orderbook(session, market_id, now, bid_p, bid_q, ask_p, ask_q)
        return True
    return False


def _get_latest_trade_ts(session, market_id: str) -> datetime | None:
    """Get the latest trade timestamp for a market."""
    row = session.execute(
        sa_text("SELECT MAX(ts) FROM trades WHERE market_id = :m"),
        {"m": market_id},
    ).fetchone()
    if row and row[0]:
        ts_val = row[0]
        if isinstance(ts_val, str):
            try:
                return datetime.fromisoformat(ts_val).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None
        if isinstance(ts_val, datetime):
            if ts_val.tzinfo is None:
                return ts_val.replace(tzinfo=timezone.utc)
            return ts_val
    return None


async def collect_from_api():
    """Collect markets and sample data from Polymarket API."""
    rate_delay = 60.0 / max(API_RATE_LIMIT, 10) if API_RATE_LIMIT else 0.1
    client = PolymarketClient(POLYMARKET_GAMMA_API, POLYMARKET_CLOB_API, rate_limit_delay=rate_delay)
    session = SessionLocal()
    try:  # noqa: SIM117
        events = await client.get_events_paginated(
            active=True, closed=False, limit_per_page=100, max_pages=5,
        )
        markets = markets_from_events(events)
        for m in markets:
            market_id = _extract_market_id(m)
            if not market_id:
                continue
            upsert_market(session, {**m, "id": market_id})

        session.commit()
        logger.info("Upserted %d markets from %d events", len(markets), len(events))

        now = datetime.now(timezone.utc)
        loaded = 0
        ob_loaded = 0

        target_markets = markets
        if COLLECT_MARKETS_LIMIT > 0:
            target_markets = markets[:COLLECT_MARKETS_LIMIT]

        for m in target_markets:
            mid = _extract_market_id(m)
            if not mid:
                continue

            token_ids = _parse_clob_token_ids(m.get("clobTokenIds"))
            asset_id = token_ids[0] if token_ids else mid

            real_trades_loaded = 0
            try:
                raw_trades = await client.get_trades(market_id=mid, limit=100)
                for rt in raw_trades:
                    ts_raw = rt.get("t") or rt.get("timestamp") or rt.get("ts") or rt.get("match_time")
                    if ts_raw is None:
                        continue
                    if isinstance(ts_raw, str):
                        try:
                            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue
                    else:
                        ts = datetime.fromtimestamp(
                            ts_raw / 1000 if ts_raw > 1e12 else ts_raw, tz=timezone.utc
                        )
                    price = float(rt.get("price", 0))
                    if price <= 0 or price >= 1:
                        continue
                    size = float(rt.get("size", rt.get("amount", 1.0)))
                    side = str(rt.get("side", rt.get("type", "buy"))).lower()
                    if side not in ("buy", "sell"):
                        side = "buy"
                    insert_trade(session, mid, ts, price, size, side)
                    real_trades_loaded += 1
                    loaded += 1
            except Exception as e:
                logger.debug("CLOB trades for %s unavailable: %s", mid, e)

            if real_trades_loaded == 0:
                history = []
                try:
                    history = await client.get_prices_history(asset_id, interval="max")
                except Exception as e:
                    logger.debug("Price history for %s unavailable: %s", mid, e)
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
                    price_val = None
                    last_trade = m.get("lastTradePrice")
                    if last_trade is not None:
                        try:
                            price_val = float(last_trade)
                        except (TypeError, ValueError):
                            price_val = None
                    if price_val is None or not (0 < price_val < 1):
                        price_val = _parse_outcome_prices(m.get("outcomePrices"))
                    if price_val is not None and 0 < price_val < 1:
                        insert_trade(session, mid, now, price_val, 1.0, "buy")
                        loaded += 1

            ob_ok = await _collect_orderbook(client, session, m, mid, asset_id, now)
            if ob_ok:
                ob_loaded += 1

            upsert_fee_rate(session, asset_id, DEFAULT_FEE_BPS)

            await asyncio.sleep(0.1)
        if loaded or ob_loaded:
            session.commit()
            logger.info(
                "Loaded %d price points, %d orderbook snapshots from API",
                loaded, ob_loaded,
            )
        else:
            logger.warning("No price points or orderbook data loaded from API")
    except Exception as e:
        session.rollback()
        logger.exception("Collect error: %s", e)
        raise
    finally:
        await client.close()
        session.close()


async def main():
    """Collector entry point."""
    logger.info("Data Collector starting")
    await collect_from_api()
    logger.info("Data Collector finished")


if __name__ == "__main__":
    asyncio.run(main())
