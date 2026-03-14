"""ML Module - train models and produce signals."""
import logging
import os
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
    impute_features,
    FEATURE_COLS,
)
from services.feature_store.features import compute_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ML_MARKETS_LIMIT = int(os.getenv("ML_MARKETS_LIMIT", "20"))
ML_TARGET_HORIZON = int(os.getenv("ML_TARGET_HORIZON", "5"))
MIN_PRICE_STD = float(os.getenv("MIN_PRICE_STD", "0.002"))
_INSERT_BATCH_SIZE = 500


def load_trades_with_target(session, market_id: str, limit: int = 5000) -> pd.DataFrame:
    """Load trades and compute target: 1 if price goes up within the next N periods.

    Uses a rolling forward max to detect upward moves within the horizon,
    producing a more balanced target distribution.
    """
    result = session.execute(
        text("SELECT ts, price, size FROM trades WHERE market_id = :m ORDER BY ts"),
        {"m": market_id},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "price", "size"])

    price_std = df["price"].std()
    if price_std < MIN_PRICE_STD:
        logger.debug("Market %s: price std %.6f < %.6f, skipping", market_id[:16], price_std, MIN_PRICE_STD)
        return pd.DataFrame()

    df = compute_all(df)

    horizon = ML_TARGET_HORIZON
    future_max = df["price"].shift(-1).rolling(window=horizon, min_periods=1).max().shift(-horizon + 1)
    df["target"] = (future_max > df["price"]).astype(int)
    df = df.dropna(subset=["target"])
    df = df.iloc[:-horizon]
    return df.tail(limit)


def _get_liquid_markets(session) -> list[str]:
    """Get markets that have orderbook data (liquid), ordered by trade count."""
    result = session.execute(text(
        "SELECT t.market_id, COUNT(*) as cnt "
        "FROM trades t "
        "INNER JOIN (SELECT DISTINCT market_id FROM orderbook) ob "
        "ON t.market_id = ob.market_id "
        "WHERE t.market_id NOT LIKE '0x_demo%' "
        "GROUP BY t.market_id "
        "ORDER BY cnt DESC"
    ))
    markets = [r[0] for r in result.fetchall()]
    if not markets:
        result = session.execute(text(
            "SELECT market_id, COUNT(*) as cnt FROM trades "
            "WHERE market_id NOT LIKE '0x_demo%' "
            "GROUP BY market_id ORDER BY cnt DESC"
        ))
        markets = [r[0] for r in result.fetchall()]
    return markets


def run():
    """Train baseline model and save out-of-sample signals only."""
    session = SessionLocal()
    try:
        markets = _get_liquid_markets(session)
        if not markets:
            logger.info("No markets with trades found")
            return

        pending_signals: list[dict] = []
        skipped_flat = 0
        skipped_single_class = 0

        for mid in markets[:ML_MARKETS_LIMIT]:
            try:
                df = load_trades_with_target(session, mid)
                if df.empty or len(df) < 20:
                    skipped_flat += 1
                    continue
                available = [c for c in FEATURE_COLS if c in df.columns]
                if not available:
                    continue
                X, y = prepare_xy(df, "target")
                if len(y.unique()) < 2:
                    skipped_single_class += 1
                    logger.debug("Market %s: single class in target, skipping", mid[:16])
                    continue
                n_splits = min(5, max(2, len(X) // 20))
                metrics = walk_forward_validate(X, y, n_splits=n_splits, model_type="logistic")
                logger.info(
                    "Market %s: AUC=%.3f P=%.3f R=%.3f (n=%d, target_balance=%.2f)",
                    mid[:16], metrics["roc_auc"], metrics["precision"], metrics["recall"],
                    len(X), y.mean(),
                )

                split_idx = int(len(X) * 0.8)
                if split_idx < 5:
                    continue
                X_train_raw, X_oos_raw = X.iloc[:split_idx], X.iloc[split_idx:]
                y_train = y.iloc[:split_idx]
                if X_oos_raw.empty:
                    continue
                X_train, train_medians = impute_features(X_train_raw)
                X_oos, _ = impute_features(X_oos_raw, medians=train_medians)
                model = train_baseline(X_train, y_train, "logistic")
                proba = model.predict_proba(X_oos)[:, 1]
                ts_oos = df["ts"].iloc[split_idx:]
                for ts, p in zip(ts_oos, proba):
                    pending_signals.append({"ts": ts, "m": mid, "p": float(p)})
            except Exception as e:
                logger.warning("Market %s: ML failed: %s", mid[:16], e)

        if skipped_flat or skipped_single_class:
            logger.info(
                "Skipped %d flat-price markets, %d single-class markets",
                skipped_flat, skipped_single_class,
            )

        updated_markets = list({s["m"] for s in pending_signals})
        for mid in updated_markets:
            session.execute(
                text("DELETE FROM signals WHERE market_id = :m"),
                {"m": mid},
            )
        stmt = text("INSERT INTO signals (ts, market_id, prediction) VALUES (:ts, :m, :p)")
        for i in range(0, len(pending_signals), _INSERT_BATCH_SIZE):
            session.execute(stmt, pending_signals[i : i + _INSERT_BATCH_SIZE])
        session.commit()
        logger.info("Signals updated for %d markets: %d new signals", len(updated_markets), len(pending_signals))
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
