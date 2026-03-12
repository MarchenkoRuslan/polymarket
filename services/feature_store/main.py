"""Feature Store - computes and caches features from trades/orderbook."""
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db import SessionLocal
from services.feature_store.features import compute_all, to_feature_rows

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_trades_by_market(session, market_id: str, limit: int = 10000) -> pd.DataFrame:
    """Load trades for a market as DataFrame."""
    result = session.execute(
        text("SELECT ts, price, size, side FROM trades WHERE market_id = :m ORDER BY ts"),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "price", "size", "side"])
    df["price"] = df["price"].astype(float)
    df["size"] = df["size"].astype(float)
    return df.tail(limit)


def save_features(session, rows: list[dict]) -> None:
    """Batch insert features."""
    for r in rows:
        session.execute(
            text("""
                INSERT INTO features (market_id, ts, feature_name, feature_value)
                VALUES (:market_id, :ts, :feature_name, :feature_value)
            """),
            r,
        )


def run(session):
    """Compute features for all markets with trades."""
    result = session.execute(text("SELECT DISTINCT market_id FROM trades LIMIT 50"))
    markets = [r[0] for r in result.fetchall()]
    for mid in markets:
        df = load_trades_by_market(session, mid)
        if df.empty or len(df) < 5:
            continue
        df = compute_all(df)
        rows = to_feature_rows(df, mid)
        stmt = text("""
            INSERT INTO features (market_id, ts, feature_name, feature_value)
            VALUES (:market_id, :ts, :feature_name, :feature_value)
        """)
        for r in rows:
            session.execute(stmt, r)
        session.commit()
        logger.info("Features for %s: %d rows", mid[:16], len(rows))


def main():
    logger.info("Feature Store starting")
    session = SessionLocal()
    try:
        run(session)
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
    finally:
        session.close()
    logger.info("Feature Store finished")


if __name__ == "__main__":
    main()
