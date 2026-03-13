"""Feature Store - computes and caches features from trades/orderbook."""
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db import SessionLocal
from services.feature_store.features import compute_all, to_feature_rows

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEATURE_MARKETS_LIMIT = int(os.getenv("FEATURE_MARKETS_LIMIT", "50"))
_INSERT_BATCH_SIZE = 500


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
    return df.tail(limit)


def _batch_insert_features(session, rows: list[dict]) -> None:
    """Insert feature rows in batches for performance."""
    stmt = text(
        "INSERT INTO features (market_id, ts, feature_name, feature_value) "
        "VALUES (:market_id, :ts, :feature_name, :feature_value)"
    )
    for i in range(0, len(rows), _INSERT_BATCH_SIZE):
        batch = rows[i : i + _INSERT_BATCH_SIZE]
        session.execute(stmt, batch)


def run(session):
    """Compute features for all markets with trades."""
    result = session.execute(
        text("SELECT DISTINCT market_id FROM trades WHERE market_id NOT LIKE '0x_demo%'"),
    )
    markets = [r[0] for r in result.fetchall()]
    if not markets:
        result = session.execute(text("SELECT DISTINCT market_id FROM trades"))
        markets = [r[0] for r in result.fetchall()]
    for mid in markets[:FEATURE_MARKETS_LIMIT]:
        df = load_trades_by_market(session, mid)
        if df.empty or len(df) < 5:
            continue
        df = compute_all(df)
        rows = to_feature_rows(df, mid)
        session.execute(
            text("DELETE FROM features WHERE market_id = :m"),
            {"m": mid},
        )
        _batch_insert_features(session, rows)
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
