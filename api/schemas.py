"""Pydantic schemas for API responses."""
from datetime import datetime

from pydantic import BaseModel


class MarketOut(BaseModel):
    """Market response model."""

    market_id: str
    event: str | None = None
    question: str | None = None
    end_date: datetime | None = None
    outcome_settled: bool | None = None


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


class OrderbookOut(BaseModel):
    """Orderbook snapshot response model."""

    id: int
    ts: datetime
    market_id: str
    bid_price: float
    bid_qty: float
    ask_price: float
    ask_qty: float


class OrderbookList(BaseModel):
    """Paginated orderbook response."""

    items: list[OrderbookOut]
    total: int


class SignalOut(BaseModel):
    """Signal response model."""

    id: int
    ts: datetime
    market_id: str
    prediction: float


class SignalsList(BaseModel):
    """Paginated signals response."""

    items: list[SignalOut]
    total: int


class StatusOut(BaseModel):
    """Status response."""

    db_ok: bool
    markets: int
    trades: int
    orderbook: int = 0
    features: int = 0
    signals: int = 0
    migration_error: str | None = None
    last_collect_error: str | None = None
    last_features_error: str | None = None
    last_ml_error: str | None = None
    last_pipeline_error: str | None = None
    db_error: str | None = None
