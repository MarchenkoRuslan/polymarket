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
    signal_label: str = "hold"


class SignalsList(BaseModel):
    """Paginated signals response."""

    items: list[SignalOut]
    total: int


class FeatureOut(BaseModel):
    """Feature row response model."""

    id: int
    market_id: str
    ts: datetime
    feature_name: str
    feature_value: float


class FeaturesList(BaseModel):
    """Paginated features response."""

    items: list[FeatureOut]
    total: int


class NewsOut(BaseModel):
    """News item response model."""

    id: int
    ts: datetime
    source: str
    title: str | None = None
    link: str | None = None
    summary: str | None = None


class NewsList(BaseModel):
    """Paginated news response."""

    items: list[NewsOut]
    total: int


class ResultOut(BaseModel):
    """Backtest result response model."""

    id: int
    ts: datetime
    market_id: str
    profit: float
    run_id: str | None = None


class ResultsList(BaseModel):
    """Paginated results response."""

    items: list[ResultOut]
    total: int


class AnalyticsOut(BaseModel):
    """Aggregated analytics for dashboard."""

    trade_stats: list[dict] = []
    feature_summary: list[dict] = []
    signal_distribution: list[dict] = []
    feature_correlations: list[dict] = []
    pnl_timeline: list[dict] = []
    spread_timeline: list[dict] = []
    total_profit: float = 0.0
    total_trades: int = 0
    total_volume: float = 0.0
    avg_spread_bps: float = 0.0
    avg_prediction: float = 0.0


class StatusOut(BaseModel):
    """Status response."""

    db_ok: bool
    markets: int
    trades: int
    orderbook: int = 0
    features: int = 0
    signals: int = 0
    news: int = 0
    fee_rates: int = 0
    orders: int = 0
    results: int = 0
    migration_error: str | None = None
    last_collect_error: str | None = None
    last_features_error: str | None = None
    last_ml_error: str | None = None
    last_pipeline_error: str | None = None
    db_error: str | None = None
