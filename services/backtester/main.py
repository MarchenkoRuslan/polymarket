"""Backtester - simulates trading on historical data."""
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db import SessionLocal
from services.backtester.engine import (
    run_backtest,
    BacktestConfig,
    baseline_always_buy,
)
from config import DEFAULT_FEE_BPS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_signals(session, market_id: str, limit: int = 5000) -> pd.Series:
    """Load model signals (predictions) for market."""
    result = session.execute(
        text("""
            SELECT ts, prediction FROM signals
            WHERE market_id = :m ORDER BY ts
        """),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.Series()
    df = pd.DataFrame(rows, columns=["ts", "prediction"])
    return (df["prediction"] >= 0.5).astype(int).replace(0, -1)  # 1=buy, -1=hold/sell


def load_market_data(session, market_id: str, limit: int = 5000) -> pd.DataFrame:
    """Load trades as OHLCV-like series (use mid price from orderbook or trade price)."""
    result = session.execute(
        text("""
            SELECT ts, price, size FROM trades
            WHERE market_id = :m ORDER BY ts
        """),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "price", "size"])
    return df.tail(limit)


def main():
    logger.info("Backtester starting")
    session = SessionLocal()
    try:
        result = session.execute(text("SELECT DISTINCT market_id FROM trades LIMIT 10"))
        markets = [r[0] for r in result.fetchall()]
        config = BacktestConfig(fee_bps=DEFAULT_FEE_BPS)

        for mid in markets:
            df = load_market_data(session, mid)
            if df.empty or len(df) < 10:
                continue
            sig_series = load_signals(session, mid, len(df))
            if sig_series.empty or len(sig_series) != len(df):
                signals = baseline_always_buy(df)
                label = "baseline"
            else:
                signals = sig_series.reindex(df.index, fill_value=0)
                label = "ML"
            bt = run_backtest(df, signals, config)
            logger.info(
                "[%s] Market %s: ROI=%.2f%%, Sharpe=%.2f, MaxDD=%.2f%%, trades=%d",
                label, mid[:16], bt.total_return * 100, bt.sharpe_ratio,
                bt.max_drawdown * 100, bt.num_trades,
            )
    except Exception as e:
        logger.exception("%s", e)
    finally:
        session.close()
    logger.info("Backtester finished")


if __name__ == "__main__":
    main()
