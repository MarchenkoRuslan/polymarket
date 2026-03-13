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
    """Train baseline model and save out-of-sample signals only."""
    session = SessionLocal()
    try:
        result = session.execute(
            text("SELECT DISTINCT market_id FROM trades WHERE market_id NOT LIKE '0x_demo%'"),
        )
        markets = [r[0] for r in result.fetchall()]
        if not markets:
            result = session.execute(text("SELECT DISTINCT market_id FROM trades"))
            markets = [r[0] for r in result.fetchall()]

        session.execute(text("DELETE FROM signals"))
        session.commit()

        for mid in markets[:20]:
            try:
                df = load_trades_with_target(session, mid)
                if df.empty or len(df) < 10:
                    continue
                available = [c for c in FEATURE_COLS if c in df.columns]
                if not available:
                    continue
                X, y = prepare_xy(df, "target")
                if len(y.unique()) < 2:
                    logger.info("Market %s: single class in target, skipping", mid[:16])
                    continue
                n_splits = min(5, max(2, len(X) // 10))
                metrics = walk_forward_validate(X, y, n_splits=n_splits, model_type="logistic")
                logger.info(
                    "Market %s: AUC=%.3f P=%.3f R=%.3f",
                    mid[:16], metrics["roc_auc"], metrics["precision"], metrics["recall"],
                )

                split_idx = int(len(X) * 0.8)
                if split_idx < 5:
                    continue
                X_train, X_oos = X.iloc[:split_idx], X.iloc[split_idx:]
                y_train = y.iloc[:split_idx]
                if X_oos.empty:
                    continue
                model = train_baseline(X_train, y_train, "logistic")
                proba = model.predict_proba(X_oos)[:, 1]
                ts_oos = df["ts"].iloc[split_idx:]
                for ts, p in zip(ts_oos, proba):
                    session.execute(
                        text("INSERT INTO signals (ts, market_id, prediction) VALUES (:ts, :m, :p)"),
                        {"ts": ts, "m": mid, "p": float(p)},
                    )
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning("Market %s: ML failed: %s", mid[:16], e)
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
