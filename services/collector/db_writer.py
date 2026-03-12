"""Write collected data to PostgreSQL."""
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def upsert_market(session: Session, market: dict) -> None:
    """Insert or update market."""
    market_id = market.get("id") or market.get("conditionId") or str(market.get("condition_id", ""))
    if not market_id:
        return
    question = market.get("question", "")
    end_date = market.get("endDate") or market.get("end_date")
    if end_date and isinstance(end_date, str):
        try:
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            end_date = None
    outcome_settled = market.get("resolved", False) or market.get("outcome_settled", False)
    event = market.get("eventId") or market.get("event_id") or ""

    session.execute(
        text("""
            INSERT INTO markets (market_id, event, question, end_date, outcome_settled)
            VALUES (:market_id, :event, :question, :end_date, :outcome_settled)
            ON CONFLICT (market_id) DO UPDATE SET
                question = EXCLUDED.question,
                end_date = EXCLUDED.end_date,
                outcome_settled = EXCLUDED.outcome_settled
        """),
        {
            "market_id": market_id,
            "event": event,
            "question": question,
            "end_date": end_date,
            "outcome_settled": outcome_settled,
        },
    )


def insert_orderbook(
    session: Session,
    market_id: str,
    ts: datetime,
    bid_price: float,
    bid_qty: float,
    ask_price: float,
    ask_qty: float,
) -> None:
    """Insert orderbook snapshot."""
    session.execute(
        text("""
            INSERT INTO orderbook (ts, market_id, bid_price, bid_qty, ask_price, ask_qty)
            VALUES (:ts, :market_id, :bid_price, :bid_qty, :ask_price, :ask_qty)
        """),
        {
            "ts": ts,
            "market_id": market_id,
            "bid_price": bid_price,
            "bid_qty": bid_qty,
            "ask_price": ask_price,
            "ask_qty": ask_qty,
        },
    )


def insert_trade(
    session: Session,
    market_id: str,
    ts: datetime,
    price: float,
    size: float,
    side: str,
) -> None:
    """Insert trade."""
    session.execute(
        text("""
            INSERT INTO trades (ts, market_id, price, size, side)
            VALUES (:ts, :market_id, :price, :size, :side)
        """),
        {"ts": ts, "market_id": market_id, "price": price, "size": size, "side": side},
    )


def markets_from_events(events: list[dict]) -> list[dict]:
    """Extract markets from events (nested structure). No mutation of input."""
    markets = []
    for ev in events:
        ev_markets = ev.get("markets") or ev.get("market") or []
        if isinstance(ev_markets, dict):
            ev_markets = [ev_markets]
        event_id = ev.get("id") or ev.get("slug", "")
        for m in ev_markets:
            markets.append({**m, "event_id": event_id})
    return markets
