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


def load_signals_df(session, market_id: str, limit: int = 5000) -> pd.DataFrame:
    """Load model signals (predictions) for market as DataFrame with ts index."""
    result = session.execute(
        text("""
            SELECT ts, prediction FROM signals
            WHERE market_id = :m ORDER BY ts
        """),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "prediction"])
    df["prediction"] = df["prediction"].astype(float)
    buy = (df["prediction"] >= 0.5).astype(int)
    sell = (df["prediction"] < 0.3).astype(int)
    df["signal"] = buy - sell
    return df[["ts", "signal"]].tail(limit)


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
    df["price"] = df["price"].astype(float)
    df["size"] = df["size"].astype(float)
    return df.tail(limit)


def main():
    logger.info("Backtester starting")
    session = SessionLocal()
    try:
        result = session.execute(
            text("SELECT DISTINCT market_id FROM trades WHERE market_id NOT LIKE '0x_demo%'")
        )
        markets = [r[0] for r in result.fetchall()]
        if not markets:
            result = session.execute(text("SELECT DISTINCT market_id FROM trades"))
            markets = [r[0] for r in result.fetchall()]
        markets = markets[:15]
        config = BacktestConfig(fee_bps=DEFAULT_FEE_BPS)

        for mid in markets:
            df = load_market_data(session, mid)
            if df.empty or len(df) < 10:
                continue
            sig_df = load_signals_df(session, mid, len(df))
            if sig_df.empty:
                signals = baseline_always_buy(df)
                label = "baseline"
            else:
                df_ts = df.copy()
                sig_ts = sig_df.copy()
                df_ts["ts"] = pd.to_datetime(df_ts["ts"])
                sig_ts["ts"] = pd.to_datetime(sig_ts["ts"])
                df_sorted = df_ts.sort_values("ts").reset_index(drop=True)
                sig_sorted = sig_ts.sort_values("ts")
                merged = pd.merge_asof(
                    df_sorted,
                    sig_sorted,
                    on="ts",
                    direction="backward",
                )
                signals = merged["signal"].fillna(0).astype(int)
                label = "ML"
                df = df_sorted
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
