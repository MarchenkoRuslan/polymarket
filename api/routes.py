"""API routes for markets, trades, orderbook, signals, status."""
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.schemas import (
    AnalyticsOut,
    FeatureOut,
    FeaturesList,
    MarketOut,
    MarketsList,
    NewsList,
    NewsOut,
    OrderbookList,
    OrderbookOut,
    ResultOut,
    ResultsList,
    SignalOut,
    SignalsList,
    StatusOut,
    TradeOut,
    TradesList,
)
from db import get_db
from server import _get_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["data"])

MAX_PAGE_SIZE = 1000


def _clamp_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Clamp limit to [1, MAX_PAGE_SIZE] and offset to [0, +inf)."""
    return max(1, min(limit, MAX_PAGE_SIZE)), max(0, offset)


def _safe_float(val, default: float = 0.0) -> float:
    """Convert to float safely, returning default for None."""
    if val is None:
        return default
    return float(val)


def _polymarket_url(slug: str | None) -> str | None:
    if slug:
        return f"https://polymarket.com/event/{slug}"
    return None


def _get_markets(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    with_signals: bool = False,
) -> MarketsList:
    limit, offset = _clamp_pagination(limit, offset)

    if with_signals:
        total = session.execute(text(
            "SELECT COUNT(DISTINCT m.market_id) FROM markets m "
            "INNER JOIN signals s ON m.market_id = s.market_id"
        )).scalar() or 0
        rows = session.execute(
            text(
                "SELECT m.market_id, m.event, m.question, m.slug, m.end_date, m.outcome_settled "
                "FROM markets m INNER JOIN ("
                "  SELECT DISTINCT market_id FROM signals"
                ") s ON m.market_id = s.market_id "
                "ORDER BY m.market_id LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
    else:
        total = session.execute(text("SELECT COUNT(*) FROM markets")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT market_id, event, question, slug, end_date, outcome_settled "
                "FROM markets ORDER BY market_id LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()

    items = [
        MarketOut(
            market_id=r[0],
            event=r[1],
            question=r[2],
            slug=r[3],
            polymarket_url=_polymarket_url(r[3]),
            end_date=r[4],
            outcome_settled=r[5],
        )
        for r in rows
    ]
    return MarketsList(items=items, total=total)


def _get_market(session: Session, market_id: str) -> MarketOut | None:
    row = session.execute(
        text(
            "SELECT market_id, event, question, slug, end_date, outcome_settled "
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
        slug=row[3],
        polymarket_url=_polymarket_url(row[3]),
        end_date=row[4],
        outcome_settled=row[5],
    )


def _get_trades(session: Session, market_id: str | None, limit: int = 100, offset: int = 0) -> TradesList:
    limit, offset = _clamp_pagination(limit, offset)
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
        TradeOut(
            id=r[0], ts=r[1], market_id=r[2],
            price=_safe_float(r[3]), size=_safe_float(r[4]), side=r[5] or "",
        )
        for r in rows
    ]
    return TradesList(items=items, total=total)


def _get_orderbook(session: Session, market_id: str | None, limit: int = 100, offset: int = 0) -> OrderbookList:
    limit, offset = _clamp_pagination(limit, offset)
    if market_id:
        total = session.execute(
            text("SELECT COUNT(*) FROM orderbook WHERE market_id = :m"),
            {"m": market_id},
        ).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, market_id, bid_price, bid_qty, ask_price, ask_qty "
                "FROM orderbook WHERE market_id = :m ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"m": market_id, "lim": limit, "off": offset},
        ).fetchall()
    else:
        total = session.execute(text("SELECT COUNT(*) FROM orderbook")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, market_id, bid_price, bid_qty, ask_price, ask_qty "
                "FROM orderbook ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
    items = [
        OrderbookOut(
            id=r[0], ts=r[1], market_id=r[2],
            bid_price=_safe_float(r[3]), bid_qty=_safe_float(r[4]),
            ask_price=_safe_float(r[5]), ask_qty=_safe_float(r[6]),
        )
        for r in rows
    ]
    return OrderbookList(items=items, total=total)


BUY_THRESHOLD = 0.55
SELL_THRESHOLD = 0.35


def _signal_label(prediction: float) -> str:
    """Classify prediction into buy/hold/sell using backtester-aligned thresholds."""
    if prediction >= BUY_THRESHOLD:
        return "buy"
    if prediction < SELL_THRESHOLD:
        return "sell"
    return "hold"


def _get_signals(session: Session, market_id: str | None, limit: int = 100, offset: int = 0) -> SignalsList:
    limit, offset = _clamp_pagination(limit, offset)
    if market_id:
        total = session.execute(
            text("SELECT COUNT(*) FROM signals WHERE market_id = :m"),
            {"m": market_id},
        ).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, market_id, prediction "
                "FROM signals WHERE market_id = :m ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"m": market_id, "lim": limit, "off": offset},
        ).fetchall()
    else:
        total = session.execute(text("SELECT COUNT(*) FROM signals")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, market_id, prediction "
                "FROM signals ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
    items = [
        SignalOut(
            id=r[0], ts=r[1], market_id=r[2],
            prediction=_safe_float(r[3]),
            signal_label=_signal_label(_safe_float(r[3])),
        )
        for r in rows
    ]
    return SignalsList(items=items, total=total)


def _get_status_response() -> StatusOut:
    data = _get_status()
    return StatusOut(
        db_ok=data["db_ok"],
        markets=data["markets"],
        trades=data["trades"],
        orderbook=data.get("orderbook", 0),
        features=data.get("features", 0),
        signals=data.get("signals", 0),
        news=data.get("news", 0),
        fee_rates=data.get("fee_rates", 0),
        orders=data.get("orders", 0),
        results=data.get("results", 0),
        migration_error=data.get("migration_error"),
        last_collect_error=data.get("last_collect_error"),
        last_features_error=data.get("last_features_error"),
        last_ml_error=data.get("last_ml_error"),
        last_pipeline_error=data.get("last_pipeline_error"),
        db_error=data.get("db_error"),
    )


@router.get("/markets", response_model=MarketsList)
def list_markets(
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    with_signals: bool = Query(default=False, description="Only return markets that have ML predictions"),
):
    """List markets with pagination. Use with_signals=true to show only markets with predictions."""
    return _get_markets(session, limit=limit, offset=offset, with_signals=with_signals)


@router.get("/markets/{market_id}", response_model=MarketOut)
def get_market(market_id: str, session: Session = Depends(get_db)):
    """Get a single market by ID."""
    m = _get_market(session, market_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return m


@router.get("/trades", response_model=TradesList)
def list_trades(
    market_id: str | None = None,
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """List trades, optionally filtered by market_id."""
    return _get_trades(session, market_id=market_id, limit=limit, offset=offset)


@router.get("/orderbook", response_model=OrderbookList)
def list_orderbook(
    market_id: str | None = None,
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """List orderbook snapshots, optionally filtered by market_id."""
    return _get_orderbook(session, market_id=market_id, limit=limit, offset=offset)


@router.get("/signals", response_model=SignalsList)
def list_signals(
    market_id: str | None = None,
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """List ML signals, optionally filtered by market_id."""
    return _get_signals(session, market_id=market_id, limit=limit, offset=offset)


@router.get("/status", response_model=StatusOut)
def get_status():
    """Get DB status and pipeline error info."""
    return _get_status_response()


def _get_features(session: Session, market_id: str | None, limit: int = 500, offset: int = 0) -> FeaturesList:
    limit, offset = _clamp_pagination(limit, offset)
    if market_id:
        total = session.execute(
            text("SELECT COUNT(*) FROM features WHERE market_id = :m"), {"m": market_id},
        ).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, market_id, ts, feature_name, feature_value "
                "FROM features WHERE market_id = :m ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"m": market_id, "lim": limit, "off": offset},
        ).fetchall()
    else:
        total = session.execute(text("SELECT COUNT(*) FROM features")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, market_id, ts, feature_name, feature_value "
                "FROM features ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
    items = [
        FeatureOut(
            id=r[0], market_id=r[1], ts=r[2],
            feature_name=r[3], feature_value=_safe_float(r[4]),
        )
        for r in rows
    ]
    return FeaturesList(items=items, total=total)


def _get_news(session: Session, limit: int = 50, offset: int = 0) -> NewsList:
    limit, offset = _clamp_pagination(limit, offset)
    try:
        total = session.execute(text("SELECT COUNT(*) FROM news")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, source, title, link, summary "
                "FROM news ORDER BY ts DESC LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
    except Exception:
        return NewsList(items=[], total=0)
    items = [
        NewsOut(id=r[0], ts=r[1], source=r[2], title=r[3], link=r[4], summary=r[5])
        for r in rows
    ]
    return NewsList(items=items, total=total)


def _get_results(session: Session, market_id: str | None, limit: int = 200, offset: int = 0) -> ResultsList:
    limit, offset = _clamp_pagination(limit, offset)
    if market_id:
        total = session.execute(
            text("SELECT COUNT(*) FROM results WHERE market_id = :m"), {"m": market_id},
        ).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, market_id, profit, run_id "
                "FROM results WHERE market_id = :m ORDER BY ts LIMIT :lim OFFSET :off"
            ),
            {"m": market_id, "lim": limit, "off": offset},
        ).fetchall()
    else:
        total = session.execute(text("SELECT COUNT(*) FROM results")).scalar() or 0
        rows = session.execute(
            text(
                "SELECT id, ts, market_id, profit, run_id "
                "FROM results ORDER BY ts LIMIT :lim OFFSET :off"
            ),
            {"lim": limit, "off": offset},
        ).fetchall()
    items = [
        ResultOut(id=r[0], ts=r[1], market_id=r[2], profit=_safe_float(r[3]), run_id=r[4])
        for r in rows
    ]
    return ResultsList(items=items, total=total)


def _pearson(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient without numpy."""
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    sx = sum((xi - mx) ** 2 for xi in x) ** 0.5
    sy = sum((yi - my) ** 2 for yi in y) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def _get_analytics(session: Session) -> AnalyticsOut:
    result = AnalyticsOut()

    try:
        rows = session.execute(text(
            "SELECT t.market_id, m.question, "
            "COUNT(*) as trade_count, "
            "COALESCE(SUM(t.size), 0) as total_volume, "
            "COALESCE(AVG(t.price), 0) as avg_price, "
            "SUM(CASE WHEN t.side = 'buy' THEN 1 ELSE 0 END) as buy_count, "
            "SUM(CASE WHEN t.side = 'sell' THEN 1 ELSE 0 END) as sell_count "
            "FROM trades t "
            "LEFT JOIN markets m ON t.market_id = m.market_id "
            "GROUP BY t.market_id, m.question "
            "ORDER BY trade_count DESC LIMIT 20"
        )).fetchall()
        result.trade_stats = [
            {
                "market_id": r[0], "question": r[1], "trade_count": r[2],
                "total_volume": round(_safe_float(r[3]), 4),
                "avg_price": round(_safe_float(r[4]), 4),
                "buy_count": r[5], "sell_count": r[6],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Analytics trade_stats: %s", exc)

    try:
        rows = session.execute(text(
            "SELECT feature_name, AVG(feature_value), MIN(feature_value), "
            "MAX(feature_value), COUNT(*) "
            "FROM features GROUP BY feature_name ORDER BY feature_name"
        )).fetchall()
        result.feature_summary = [
            {
                "name": r[0],
                "mean": round(_safe_float(r[1]), 6),
                "min": round(_safe_float(r[2]), 6),
                "max": round(_safe_float(r[3]), 6),
                "count": r[4],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)

    try:
        rows = session.execute(text(
            "SELECT ROUND(prediction, 1) as bucket, COUNT(*) "
            "FROM signals GROUP BY bucket ORDER BY bucket"
        )).fetchall()
        result.signal_distribution = [
            {"bucket": _safe_float(r[0]), "count": r[1]} for r in rows
        ]
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)

    try:
        rows = session.execute(text(
            "SELECT ts, (ask_price - bid_price) as spread, "
            "CASE WHEN (ask_price + bid_price) > 0 "
            "THEN (ask_price - bid_price) / ((ask_price + bid_price) / 2.0) * 10000 "
            "ELSE 0 END as spread_bps "
            "FROM orderbook ORDER BY ts DESC LIMIT 200"
        )).fetchall()
        result.spread_timeline = [
            {
                "ts": str(r[0]),
                "spread": round(_safe_float(r[1]), 6),
                "spread_bps": round(_safe_float(r[2]), 2),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)

    try:
        rows = session.execute(text(
            "SELECT ts, market_id, profit FROM results ORDER BY ts LIMIT 500"
        )).fetchall()
        cumulative = 0.0
        pnl = []
        for r in rows:
            cumulative += _safe_float(r[2])
            pnl.append({
                "ts": str(r[0]), "market_id": r[1],
                "profit": round(_safe_float(r[2]), 4),
                "cumulative": round(cumulative, 4),
            })
        result.pnl_timeline = pnl
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)

    try:
        result.total_trades = session.execute(text("SELECT COUNT(*) FROM trades")).scalar() or 0
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)
    try:
        result.total_volume = round(
            _safe_float(session.execute(text("SELECT COALESCE(SUM(size), 0) FROM trades")).scalar()), 4
        )
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)
    try:
        result.total_profit = round(
            _safe_float(session.execute(text("SELECT COALESCE(SUM(profit), 0) FROM results")).scalar()), 4
        )
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)
    try:
        result.avg_prediction = round(
            _safe_float(session.execute(text("SELECT COALESCE(AVG(prediction), 0) FROM signals")).scalar()), 4
        )
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)
    try:
        result.avg_spread_bps = round(
            _safe_float(session.execute(text(
                "SELECT COALESCE(AVG("
                "CASE WHEN (ask_price + bid_price) > 0 "
                "THEN (ask_price - bid_price) / ((ask_price + bid_price) / 2.0) * 10000 "
                "ELSE 0 END), 0) FROM orderbook"
            )).scalar()), 2
        )
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)

    try:
        feat_rows = session.execute(text(
            "SELECT market_id, ts, feature_name, feature_value "
            "FROM features ORDER BY market_id, ts LIMIT 5000"
        )).fetchall()
        points: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        for r in feat_rows:
            points[(r[0], str(r[1]))][r[2]] = _safe_float(r[3])
        all_features = sorted({fn for pt in points.values() for fn in pt})
        correlations = []
        for i, f1 in enumerate(all_features):
            for f2 in all_features[i + 1:]:
                v1, v2 = [], []
                for pt in points.values():
                    if f1 in pt and f2 in pt:
                        v1.append(pt[f1])
                        v2.append(pt[f2])
                if len(v1) >= 5:
                    corr = _pearson(v1, v2)
                    correlations.append({
                        "feature_1": f1, "feature_2": f2,
                        "correlation": round(corr, 3),
                    })
        result.feature_correlations = correlations
    except Exception as exc:
        logger.debug("Analytics query error: %s", exc)

    return result


@router.get("/features", response_model=FeaturesList)
def list_features(
    market_id: str | None = None,
    session: Session = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """List computed features, optionally filtered by market_id."""
    return _get_features(session, market_id=market_id, limit=limit, offset=offset)


@router.get("/news", response_model=NewsList)
def list_news(
    session: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """List news items."""
    return _get_news(session, limit=limit, offset=offset)


@router.get("/results", response_model=ResultsList)
def list_results(
    market_id: str | None = None,
    session: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """List backtest results, optionally filtered by market_id."""
    return _get_results(session, market_id=market_id, limit=limit, offset=offset)


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(session: Session = Depends(get_db)):
    """Computed analytics: trade stats, feature correlations, signal distribution, PnL."""
    return _get_analytics(session)
