"""Backtester - simulates trading on historical data."""
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db import SessionLocal
from services.backtester.engine import (
    run_backtest,
    BacktestConfig,
    BacktestResult,
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
    # 1=buy, 0=hold, -1=sell (pred>=0.5 buy, pred<0.3 sell, else hold)
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
    return df.tail(limit)


def save_result(
    session, market_id: str, bt: BacktestResult, run_id: str,
) -> None:
    """Persist backtest result to the results table."""
    session.execute(
        text("""
            INSERT INTO results (ts, market_id, profit, run_id)
            VALUES (:ts, :market_id, :profit, :run_id)
        """),
        {
            "ts": datetime.now(timezone.utc),
            "market_id": market_id,
            "profit": bt.total_return,
            "run_id": run_id,
        },
    )


def main():
    logger.info("Backtester starting")
    session = SessionLocal()
    run_id = uuid.uuid4().hex[:12]
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
            save_result(session, mid, bt, run_id)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
    finally:
        session.close()
    logger.info("Backtester finished (run_id=%s)", run_id)


if __name__ == "__main__":
    main()
