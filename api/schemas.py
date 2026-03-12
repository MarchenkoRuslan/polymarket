"""Pydantic schemas for API responses."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarketOut(BaseModel):
    """Market response model."""

    market_id: str
    event: Optional[str] = None
    question: Optional[str] = None
    end_date: Optional[datetime] = None
    outcome_settled: Optional[bool] = None


class TradeOut(BaseModel):
    """Trade response model."""

    id: int
    ts: datetime
    market_id: str
    price: float
    size: float
    side: str


class MarketsList(BaseModel):
    """Paginated markets response."""

    items: list[MarketOut]
    total: int


class TradesList(BaseModel):
    """Paginated trades response."""

    items: list[TradeOut]
    total: int


class StatusOut(BaseModel):
    """Status response."""

    db_ok: bool
    markets: int
    trades: int
    last_collect_error: Optional[str] = None
    db_error: Optional[str] = None
