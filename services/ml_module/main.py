"""ML Module - train models and produce signals."""
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db import SessionLocal
from services.ml_module.models import (
    train_baseline,
    walk_forward_validate,
    prepare_xy,
    FEATURE_COLS,
)
from services.feature_store.features import compute_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_features_wide(session, market_id: str, limit: int = 5000) -> pd.DataFrame:
    """Load features as wide DataFrame (one row per ts)."""
    result = session.execute(
        text("""
            SELECT ts, feature_name, feature_value FROM features
            WHERE market_id = :m ORDER BY ts
        """),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "feature_name", "feature_value"])
    pivot = df.pivot_table(index="ts", columns="feature_name", values="feature_value")
    return pivot.tail(limit)


def load_trades_with_target(session, market_id: str, limit: int = 5000) -> pd.DataFrame:
    """Load trades and compute target: 1 if price goes up in next period."""
    result = session.execute(
        text("SELECT ts, price, size FROM trades WHERE market_id = :m ORDER BY ts"),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "price", "size"])
    df = compute_all(df)
    df["target"] = (df["price"].shift(-1) > df["price"]).astype(int)
    df = df.dropna(subset=["target"])
    return df.tail(limit)


def run():
    """Train baseline model and save signals."""
    session = SessionLocal()
    try:
        result = session.execute(
            text("SELECT DISTINCT market_id FROM trades WHERE market_id NOT LIKE '0x_demo%'"),
        )
        markets = [r[0] for r in result.fetchall()]
        if not markets:
            result = session.execute(text("SELECT DISTINCT market_id FROM trades"))
            markets = [r[0] for r in result.fetchall()]
        for mid in markets[:20]:
            df = load_trades_with_target(session, mid)
            if df.empty or len(df) < 10:
                continue
            available = [c for c in FEATURE_COLS if c in df.columns]
            if not available:
                continue
            X, y = prepare_xy(df, "target")
            metrics = walk_forward_validate(X, y, n_splits=3, model_type="logistic")
            logger.info("Market %s: AUC=%.3f P=%.3f R=%.3f", mid[:16], metrics["roc_auc"], metrics["precision"], metrics["recall"])
            model = train_baseline(X, y, "logistic")
            proba = model.predict_proba(X)[:, 1]
            for i, (ts, p) in enumerate(zip(df["ts"], proba)):
                session.execute(
                    text("INSERT INTO signals (ts, market_id, prediction) VALUES (:ts, :m, :p)"),
                    {"ts": ts, "m": mid, "p": float(p)},
                )
            session.commit()
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
    finally:
        session.close()


def main():
    logger.info("ML Module starting")
    run()
    logger.info("ML Module finished")


if __name__ == "__main__":
    main()
