"""Tests for feature computation."""
import pandas as pd

from services.feature_store.features import (
    compute_price_features,
    compute_volume_features,
    compute_spread_features,
    compute_rsi,
    to_feature_rows,
)


def test_compute_price_features():
    """Price features are computed."""
    df = pd.DataFrame({"price": [0.5, 0.51, 0.49, 0.52, 0.48] * 20})
    out = compute_price_features(df)
    assert "ma_1h" in out.columns
    assert "volatility_1h" in out.columns
    assert "roc_1h" in out.columns
    assert "rsi_14" in out.columns
    assert "macd" in out.columns


def test_compute_volume_features():
    """Volume features are computed."""
    df = pd.DataFrame({"size": [10.0, 20.0, 15.0] * 10})
    out = compute_volume_features(df)
    assert "volume_1h" in out.columns
    assert "volume_5m" in out.columns


def test_compute_spread_features():
    """Spread features from bid/ask."""
    df = pd.DataFrame({
        "bid_price": [0.49, 0.50, 0.51],
        "ask_price": [0.51, 0.52, 0.53],
    })
    out = compute_spread_features(df)
    assert "spread" in out.columns
    assert "spread_bps" in out.columns
    assert abs(out["spread"].iloc[0] - 0.02) < 1e-6


def test_compute_rsi():
    """RSI in [0, 100]."""
    s = pd.Series([0.5 + 0.01 * (i % 5) for i in range(30)])
    rsi = compute_rsi(s, period=14)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_to_feature_rows():
    """Feature rows are exported correctly."""
    df = pd.DataFrame({
        "ts": [1, 2],
        "ma_1h": [0.5, 0.51],
        "volatility_1h": [0.01, 0.02],
    })
    rows = to_feature_rows(df, "market-123")
    assert len(rows) >= 2
    assert all(r["market_id"] == "market-123" for r in rows)
