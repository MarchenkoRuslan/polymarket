"""Integration tests: full pipeline collector -> features -> ml -> backtest."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import text


@pytest.fixture
def db_session(sqlite_db):
    """Provide a session for tests."""
    engine, Session = sqlite_db
    session = Session()
    yield session
    session.close()


def test_pipeline_collector_to_features(db_session):
    """Insert trades via db_writer -> run feature store logic."""
    from services.collector.db_writer import insert_trade, upsert_market
    from services.feature_store.features import compute_all, to_feature_rows

    upsert_market(db_session, {
        "id": "m1",
        "question": "Test?",
        "event_id": "e1",
        "outcome_settled": False,
    })
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(100):
        ts = base + timedelta(minutes=i)
        price = 0.5 + 0.001 * (i % 20)
        insert_trade(db_session, "m1", ts, price, 10.0 + i, "buy")
    db_session.commit()

    result = db_session.execute(text("SELECT ts, price, size FROM trades WHERE market_id = 'm1' ORDER BY ts"))
    rows = result.fetchall()
    df = pd.DataFrame(rows, columns=["ts", "price", "size"])
    df = compute_all(df)
    rows_out = to_feature_rows(df, "m1")
    assert len(rows_out) > 0
    assert any(r["feature_name"] == "ma_1h" for r in rows_out)


def test_pipeline_features_to_ml(db_session):
    """Insert trades + features -> ML produces signals."""
    from services.collector.db_writer import insert_trade, upsert_market
    from services.feature_store.features import compute_all
    from services.ml_module.models import FEATURE_COLS, prepare_xy, impute_features, train_baseline, walk_forward_validate

    upsert_market(db_session, {"id": "m2", "question": "Q2", "event_id": "e1", "outcome_settled": False})
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(80):
        ts = base + timedelta(minutes=i)
        price = 0.5 + 0.002 * (i % 10)
        insert_trade(db_session, "m2", ts, price, 5.0, "buy")
    db_session.commit()

    result = db_session.execute(text("SELECT ts, price, size FROM trades WHERE market_id = 'm2' ORDER BY ts"))
    df = pd.DataFrame(result.fetchall(), columns=["ts", "price", "size"])
    df = compute_all(df)
    df["target"] = (df["price"].shift(-1) > df["price"]).astype(int)
    df = df.dropna(subset=["target"])
    available = [c for c in FEATURE_COLS if c in df.columns]
    assert len(available) >= 2
    X, y = prepare_xy(df, "target")
    metrics = walk_forward_validate(X, y, n_splits=3)
    assert "roc_auc" in metrics
    X_imputed, _ = impute_features(X)
    model = train_baseline(X_imputed, y)
    assert model is not None


def test_pipeline_backtest_with_signals(db_session):
    """Insert trades -> backtester runs with baseline signals."""
    from services.collector.db_writer import insert_trade, upsert_market
    from services.backtester.engine import run_backtest, BacktestConfig, baseline_always_buy

    upsert_market(db_session, {"id": "m3", "question": "Q3", "event_id": "e1", "outcome_settled": False})
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(50):
        ts = base + timedelta(minutes=i)
        insert_trade(db_session, "m3", ts, 0.5 + i * 0.001, 10.0, "buy")
    db_session.commit()

    result = db_session.execute(text("SELECT ts, price, size FROM trades WHERE market_id = 'm3' ORDER BY ts"))
    df = pd.DataFrame(result.fetchall(), columns=["ts", "price", "size"])
    signals = baseline_always_buy(df)
    config = BacktestConfig(initial_capital=1000, fee_bps=30)
    bt = run_backtest(df, signals, config)
    assert bt.num_trades >= 0
    assert bt.total_return is not None
    assert len(bt.equity_curve) > 0


def test_db_writer_upsert_market(db_session):
    """db_writer upsert_market inserts and updates."""
    from services.collector.db_writer import upsert_market

    upsert_market(db_session, {
        "id": "mid1",
        "question": "First",
        "event_id": "e1",
        "outcome_settled": False,
    })
    db_session.commit()
    r = db_session.execute(text("SELECT market_id, question FROM markets WHERE market_id = 'mid1'")).fetchone()
    assert r[0] == "mid1"
    assert r[1] == "First"

    upsert_market(db_session, {
        "id": "mid1",
        "question": "Updated",
        "event_id": "e1",
        "outcome_settled": True,
    })
    db_session.commit()
    r = db_session.execute(text("SELECT question, outcome_settled FROM markets WHERE market_id = 'mid1'")).fetchone()
    assert r[0] == "Updated"
    assert r[1] == 1  # True in SQLite


def test_db_writer_insert_trade(db_session):
    """db_writer insert_trade works."""
    from services.collector.db_writer import insert_trade

    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    insert_trade(db_session, "m4", ts, 0.55, 100.0, "buy")
    db_session.commit()
    r = db_session.execute(text("SELECT market_id, price, size, side FROM trades WHERE market_id = 'm4'")).fetchone()
    assert r[0] == "m4"
    assert r[1] == 0.55
    assert r[2] == 100.0
    assert r[3] == "buy"


def test_db_writer_insert_orderbook(db_session):
    """db_writer insert_orderbook works."""
    from services.collector.db_writer import insert_orderbook

    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    insert_orderbook(db_session, "m5", ts, 0.45, 50.0, 0.55, 60.0)
    db_session.commit()
    r = db_session.execute(text("SELECT bid_price, ask_price FROM orderbook WHERE market_id = 'm5'")).fetchone()
    assert r[0] == 0.45
    assert r[1] == 0.55


def test_db_writer_upsert_fee_rate(db_session):
    """upsert_fee_rate inserts and updates fee rates."""
    from services.collector.db_writer import upsert_fee_rate

    upsert_fee_rate(db_session, "token_abc", 30)
    db_session.commit()
    r = db_session.execute(
        text("SELECT token_id, base_fee_bps FROM fee_rates WHERE token_id = 'token_abc'")
    ).fetchone()
    assert r[0] == "token_abc"
    assert r[1] == 30

    upsert_fee_rate(db_session, "token_abc", 50)
    db_session.commit()
    r = db_session.execute(
        text("SELECT base_fee_bps FROM fee_rates WHERE token_id = 'token_abc'")
    ).fetchone()
    assert r[0] == 50


def test_db_writer_upsert_fee_rate_multiple_tokens(db_session):
    """upsert_fee_rate handles multiple tokens independently."""
    from services.collector.db_writer import upsert_fee_rate

    upsert_fee_rate(db_session, "token_1", 20)
    upsert_fee_rate(db_session, "token_2", 40)
    db_session.commit()
    count = db_session.execute(text("SELECT COUNT(*) FROM fee_rates")).scalar()
    assert count == 2
    r1 = db_session.execute(
        text("SELECT base_fee_bps FROM fee_rates WHERE token_id = 'token_1'")
    ).fetchone()
    r2 = db_session.execute(
        text("SELECT base_fee_bps FROM fee_rates WHERE token_id = 'token_2'")
    ).fetchone()
    assert r1[0] == 20
    assert r2[0] == 40
