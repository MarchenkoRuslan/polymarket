"""Pydantic schemas for API responses."""
from datetime import datetime

from pydantic import BaseModel, Field


class MarketOut(BaseModel):
    """Market response model."""

    market_id: str = Field(..., examples=["0x1234abcd"])
    event: str | None = Field(None, examples=["event-123"])
    question: str | None = Field(None, examples=["Will BTC exceed $100k by EOY?"])
    slug: str | None = Field(None, examples=["will-btc-exceed-100k"])
    polymarket_url: str | None = Field(None, examples=["https://polymarket.com/event/will-btc-exceed-100k"])
    end_date: datetime | None = None
    outcome_settled: bool | None = None


class TradeOut(BaseModel):
    """Trade response model."""

    id: int = Field(..., examples=[42])
    ts: datetime
    market_id: str = Field(..., examples=["0x1234abcd"])
    price: float = Field(..., examples=[0.65], description="Outcome probability 0-1")
    size: float = Field(..., examples=[100.0], description="Trade size in shares")
    side: str = Field(..., examples=["buy"])


class MarketsList(BaseModel):
    """Paginated markets response."""

    items: list[MarketOut]
    total: int = Field(..., examples=[150])


class TradesList(BaseModel):
    """Paginated trades response."""

    items: list[TradeOut]
    total: int


class OrderbookOut(BaseModel):
    """Orderbook snapshot response model."""

    id: int
    ts: datetime
    market_id: str
    bid_price: float = Field(..., examples=[0.62])
    bid_qty: float = Field(..., examples=[500.0])
    ask_price: float = Field(..., examples=[0.65])
    ask_qty: float = Field(..., examples=[300.0])


class OrderbookList(BaseModel):
    """Paginated orderbook response."""

    items: list[OrderbookOut]
    total: int


class SignalOut(BaseModel):
    """ML signal response model."""

    id: int
    ts: datetime
    market_id: str
    prediction: float = Field(..., examples=[0.72], description="Probability of price increase (0-1)")
    signal_label: str = Field("hold", examples=["buy"], description="buy (>=0.55), sell (<0.35), hold")


class SignalsList(BaseModel):
    """Paginated signals response."""

    items: list[SignalOut]
    total: int


class FeatureOut(BaseModel):
    """Feature row response model."""

    id: int
    market_id: str
    ts: datetime
    feature_name: str = Field(..., examples=["rsi_14"])
    feature_value: float = Field(..., examples=[55.3])


class FeaturesList(BaseModel):
    """Paginated features response."""

    items: list[FeatureOut]
    total: int


class NewsOut(BaseModel):
    """News item response model."""

    id: int
    ts: datetime
    source: str = Field(..., examples=["CoinDesk"])
    title: str | None = Field(None, examples=["Bitcoin hits new high"])
    link: str | None = Field(None, examples=["https://coindesk.com/article/..."])
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
    profit: float = Field(..., examples=[0.023], description="P&L as fraction of capital")
    run_id: str | None = None


class ResultsList(BaseModel):
    """Paginated results response."""

    items: list[ResultOut]
    total: int


class TradeStatOut(BaseModel):
    """Per-market trade statistics."""

    market_id: str
    question: str | None = None
    trade_count: int = 0
    total_volume: float = 0.0
    avg_price: float = 0.0
    buy_count: int = 0
    sell_count: int = 0


class FeatureSummaryOut(BaseModel):
    """Descriptive statistics for a feature."""

    name: str
    mean: float = 0.0
    min: float = 0.0
    max: float = 0.0
    count: int = 0


class SignalBucketOut(BaseModel):
    """Signal distribution bucket."""

    bucket: float
    count: int


class FeatureCorrelationOut(BaseModel):
    """Pairwise feature correlation."""

    feature_1: str
    feature_2: str
    correlation: float


class SpreadPointOut(BaseModel):
    """Bid-ask spread data point."""

    ts: str
    spread: float
    spread_bps: float


class PnlPointOut(BaseModel):
    """P&L timeline data point."""

    ts: str
    market_id: str
    profit: float
    cumulative: float


class AnalyticsOut(BaseModel):
    """Aggregated analytics for dashboard."""

    trade_stats: list[TradeStatOut] = []
    feature_summary: list[FeatureSummaryOut] = []
    signal_distribution: list[SignalBucketOut] = []
    feature_correlations: list[FeatureCorrelationOut] = []
    pnl_timeline: list[PnlPointOut] = []
    spread_timeline: list[SpreadPointOut] = []
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
