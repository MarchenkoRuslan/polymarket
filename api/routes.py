"""API routes for markets, trades, status."""
from sqlalchemy import text

from fastapi import APIRouter, HTTPException

from api.schemas import MarketOut, MarketsList, StatusOut, TradeOut, TradesList
from db import SessionLocal

router = APIRouter(prefix="/api/v1", tags=["data"])


def _get_markets(limit: int = 100, offset: int = 0) -> MarketsList:
    session = SessionLocal()
    try:
        total = session.execute(text("SELECT COUNT(*) FROM markets")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT market_id, event, question, end_date, outcome_settled "
                "FROM markets ORDER BY market_id LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
        items = [
            MarketOut(
                market_id=r[0],
                event=r[1],
                question=r[2],
                end_date=r[3],
                outcome_settled=r[4],
            )
            for r in rows
        ]
        return MarketsList(items=items, total=total)
    finally:
        session.close()


def _get_market(market_id: str) -> MarketOut | None:
    session = SessionLocal()
    try:
        row = session.execute(
            text(
                "SELECT market_id, event, question, end_date, outcome_settled "
                "FROM markets WHERE market_id = :m"
            ),
            {"m": market_id},
        ).fetchone()
        if not row:
            return None
        return MarketOut(
            market_id=row[0],
            event=row[1],
            question=row[2],
            end_date=row[3],
            outcome_settled=row[4],
        )
    finally:
        session.close()


def _get_trades(market_id: str | None, limit: int = 100, offset: int = 0) -> TradesList:
    session = SessionLocal()
    try:
        if market_id:
            total = session.execute(
                text("SELECT COUNT(*) FROM trades WHERE market_id = :m"),
                {"m": market_id},
            ).scalar() or 0
            rows = session.execute(
                text(
                    "SELECT id, ts, market_id, price, size, side "
                    "FROM trades WHERE market_id = :m ORDER BY ts DESC LIMIT :lim OFFSET :off"
                ),
                {"m": market_id, "lim": limit, "off": offset},
            ).fetchall()
        else:
            total = session.execute(text("SELECT COUNT(*) FROM trades")).scalar() or 0
            rows = session.execute(
                text(
                    "SELECT id, ts, market_id, price, size, side "
                    "FROM trades ORDER BY ts DESC LIMIT :lim OFFSET :off"
                ),
                {"lim": limit, "off": offset},
            ).fetchall()
        items = [
            TradeOut(id=r[0], ts=r[1], market_id=r[2], price=float(r[3]), size=float(r[4]), side=r[5])
            for r in rows
        ]
        return TradesList(items=items, total=total)
    finally:
        session.close()


def _get_status_response() -> StatusOut:
    from server import _get_status
    data = _get_status()
    return StatusOut(
        db_ok=data["db_ok"],
        markets=data["markets"],
        trades=data["trades"],
        last_collect_error=data.get("last_collect_error"),
        db_error=data.get("db_error"),
    )


@router.get("/markets", response_model=MarketsList)
def list_markets(limit: int = 100, offset: int = 0):
    """List markets with pagination."""
    return _get_markets(limit=limit, offset=offset)


@router.get("/markets/{market_id}", response_model=MarketOut)
def get_market(market_id: str):
    """Get a single market by ID."""
    m = _get_market(market_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return m


@router.get("/trades", response_model=TradesList)
def list_trades(market_id: str | None = None, limit: int = 100, offset: int = 0):
    """List trades, optionally filtered by market_id."""
    return _get_trades(market_id=market_id, limit=limit, offset=offset)


@router.get("/status", response_model=StatusOut)
def get_status():
    """Get DB status and collect error info."""
    return _get_status_response()
